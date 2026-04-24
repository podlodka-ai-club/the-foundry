from __future__ import annotations

import traceback

import structlog
from langfuse import observe

from . import observability, state, worktree
from .agents import AgentSettings, AgentStage
from .agents.base import AgentTask, build_fresh_prompt
from .config import Settings
from .events import read_events, record_event, stage_span
from .models import Stage, Task, TaskStatus
from .stages import agent_implement as agent_implement_stage
from .stages import agent_plan as agent_plan_stage
from .stages import context as context_stage
from .stages import fetch as fetch_stage
from .stages import pr as pr_stage
from .stages import verify as verify_stage

log = structlog.get_logger()

# Stages before the first side-effecting step. Failures here are almost always
# infrastructure hiccups (network, auth, worktree setup) — re-queue instead of
# marking the task terminally failed.
PRE_IMPLEMENT_STAGES = {Stage.FETCH, Stage.CONTEXT, Stage.PLAN}


def _mark(settings: Settings, task: Task, *, stage: Stage, status: TaskStatus | None = None) -> Task:
    task.current_stage = stage
    if status is not None:
        task.status = status
    return state.upsert_task(settings.db_path, task)


@observe(name="task.process")
def _process_task(settings: Settings, task: Task) -> Task:
    log.info("task.start", task_id=task.id, issue=task.issue_number)

    if task.pr_url:
        log.info("task.skip_already_has_pr", task_id=task.id, pr_url=task.pr_url)
        return task

    task.attempts += 1
    task.status = TaskStatus.RUNNING
    task = state.upsert_task(settings.db_path, task)

    # `fetch` runs as a batch in `run_once` before tasks enter here, so there's
    # no `stage_span` wrapping it. Emit synthetic started/finished events so the
    # UI doesn't render fetch as "not yet executed". Idempotent on reruns after
    # reset: if a `stage_finished` for fetch already exists, don't duplicate.
    existing = read_events(settings.db_path, task_id=task.id)
    has_fetch_finished = any(
        e.stage == Stage.FETCH.value and e.kind == "stage_finished" for e in existing
    )
    if not has_fetch_finished:
        record_event(
            settings.db_path,
            task.id,
            Stage.FETCH.value,
            "stage_started",
            {"input": {"issue_number": task.issue_number, "repo": task.repo}},
        )
        record_event(
            settings.db_path,
            task.id,
            Stage.FETCH.value,
            "stage_finished",
            {
                "duration_ms": 0,
                "output": {
                    "issue_title": task.issue_title,
                    "issue_number": task.issue_number,
                },
            },
        )

    base = worktree.ensure_base_repo(settings.worktree_root, settings.source_repo)
    wt_path, branch_name = worktree.create_worktree(settings.worktree_root, task.id)
    task.worktree_path = str(wt_path)
    task.branch_name = branch_name
    task = state.upsert_task(settings.db_path, task)

    # CONTEXT
    task = _mark(settings, task, stage=Stage.CONTEXT)
    with stage_span(settings.db_path, task.id, Stage.CONTEXT.value) as finish:
        ctx = context_stage.run(task, settings)
        finish(output={"files": len(ctx.get("files", []))})
    state.append_log(settings.db_path, task.id, Stage.CONTEXT, {"ok": True})

    # PLAN
    task = _mark(settings, task, stage=Stage.PLAN)
    plan_agent_settings = AgentSettings.from_env(AgentStage.PLAN, db_path=settings.db_path)
    plan_agent_task = AgentTask(
        id=task.id or task.issue_number,
        title=task.issue_title,
        description=task.issue_body,
    )
    plan_prompt = build_fresh_prompt(AgentStage.PLAN, plan_agent_task, "")
    with stage_span(
        settings.db_path,
        task.id,
        Stage.PLAN.value,
        input={"title": task.issue_title, "prompt": plan_prompt},
        agent={"name": plan_agent_settings.backend, "model": plan_agent_settings.model},
    ) as finish:
        plan = agent_plan_stage.run(task, ctx, wt_path, settings)
        finish(
            output={"summary": plan.get("summary", ""), "text": plan.get("plan", "")},
            cost_usd=plan.get("cost_usd"),
            tokens_in=plan.get("tokens_in"),
            tokens_out=plan.get("tokens_out"),
        )
    state.append_log(settings.db_path, task.id, Stage.PLAN, {"summary": plan.get("summary", "")})

    # IMPLEMENT
    task = _mark(settings, task, stage=Stage.IMPLEMENT)
    impl_agent_settings = AgentSettings.from_env(AgentStage.IMPLEMENT, db_path=settings.db_path)
    impl_agent_task = AgentTask(
        id=task.id or task.issue_number,
        title=task.issue_title,
        description=task.issue_body,
    )
    impl_prompt = build_fresh_prompt(
        AgentStage.IMPLEMENT, impl_agent_task, plan.get("plan", "")
    )
    with stage_span(
        settings.db_path,
        task.id,
        Stage.IMPLEMENT.value,
        input={"title": task.issue_title, "prompt": impl_prompt},
        agent={"name": impl_agent_settings.backend, "model": impl_agent_settings.model},
    ) as finish:
        impl_result = agent_implement_stage.run(task, plan, wt_path, settings)
        finish(
            output={
                "summary": impl_result.get("result", ""),
                "text": impl_result.get("response", ""),
            },
            cost_usd=impl_result.get("cost_usd"),
            tokens_in=impl_result.get("tokens_in"),
            tokens_out=impl_result.get("tokens_out"),
        )
    state.append_log(settings.db_path, task.id, Stage.IMPLEMENT, impl_result)

    # VERIFY
    task = _mark(settings, task, stage=Stage.VERIFY)
    with stage_span(settings.db_path, task.id, Stage.VERIFY.value) as finish:
        verify_result = verify_stage.run(task, wt_path, settings, impl_result=impl_result)
        if not verify_result.get("passed"):
            raise RuntimeError(f"verify failed: {verify_result}")
        finish(output={"ok": True, "report": verify_result.get("report", "")})
    state.append_log(settings.db_path, task.id, Stage.VERIFY, verify_result)

    # PR
    task = _mark(settings, task, stage=Stage.PR)
    with stage_span(settings.db_path, task.id, Stage.PR.value) as finish:
        pr_result = pr_stage.run(
            task, wt_path, branch_name, settings, report=verify_result.get("report", "")
        )
        task.pr_url = pr_result["pr_url"]
        finish(output={"pr_url": pr_result["pr_url"]})
    state.append_log(settings.db_path, task.id, Stage.PR, pr_result)

    task = _mark(settings, task, stage=Stage.DONE, status=TaskStatus.DONE)
    worktree.cleanup_worktree(base, wt_path)
    log.info("task.done", task_id=task.id, pr_url=task.pr_url)
    return task


def run_once(settings: Settings) -> list[Task]:
    """Fetch pending tasks and run each through the full pipeline.

    Failures in one task do not stop the batch — they're persisted and the next
    task proceeds. Returns the final list of tasks touched in this run.
    """
    observability.init_langfuse()
    state.init_db(settings.db_path)
    tasks = fetch_stage.fetch(settings)
    log.info("run.fetched", count=len(tasks))

    processed: list[Task] = []
    for task in tasks:
        try:
            processed.append(_process_task(settings, task))
        except Exception as e:
            failed_stage = task.current_stage
            tb = traceback.format_exc()
            state.append_log(
                settings.db_path,
                task.id,
                failed_stage,
                {"error": str(e), "traceback": tb},
            )
            if failed_stage in PRE_IMPLEMENT_STAGES:
                task.status = TaskStatus.PENDING
                task.current_stage = Stage.FETCH
                log.warning(
                    "task.requeued",
                    task_id=task.id,
                    stage=failed_stage.value,
                    error=str(e),
                )
            else:
                task.status = TaskStatus.FAILED
                task.current_stage = Stage.FAILED
                log.error(
                    "task.failed",
                    task_id=task.id,
                    stage=failed_stage.value,
                    error=str(e),
                )
            state.upsert_task(settings.db_path, task)
            processed.append(task)
    observability.flush()
    return processed
