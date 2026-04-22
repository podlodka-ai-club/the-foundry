from __future__ import annotations

import traceback

import structlog

from . import state, worktree
from .config import Settings
from .models import Stage, Task, TaskStatus
from .stages import context as context_stage
from .stages import fetch as fetch_stage
from .stages import implement as implement_stage
from .stages import plan as plan_stage
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


def _process_task(settings: Settings, task: Task) -> Task:
    log.info("task.start", task_id=task.id, issue=task.issue_number)

    if task.pr_url:
        log.info("task.skip_already_has_pr", task_id=task.id, pr_url=task.pr_url)
        return task

    task.attempts += 1
    task.status = TaskStatus.RUNNING
    task = state.upsert_task(settings.db_path, task)

    base = worktree.ensure_base_repo(settings.worktree_root, settings.source_repo)
    wt_path, branch_name = worktree.create_worktree(settings.worktree_root, task.id)
    task.worktree_path = str(wt_path)
    task.branch_name = branch_name
    task = state.upsert_task(settings.db_path, task)

    # CONTEXT
    task = _mark(settings, task, stage=Stage.CONTEXT)
    ctx = context_stage.run(task, settings)
    state.append_log(settings.db_path, task.id, Stage.CONTEXT, {"ok": True})

    # PLAN
    task = _mark(settings, task, stage=Stage.PLAN)
    plan = plan_stage.run(task, ctx, settings)
    state.append_log(settings.db_path, task.id, Stage.PLAN, {"steps": len(plan.get("steps", []))})

    # IMPLEMENT
    task = _mark(settings, task, stage=Stage.IMPLEMENT)
    impl_result = implement_stage.run(task, plan, wt_path, settings)
    state.append_log(settings.db_path, task.id, Stage.IMPLEMENT, impl_result)

    # VERIFY
    task = _mark(settings, task, stage=Stage.VERIFY)
    verify_result = verify_stage.run(task, wt_path, settings)
    state.append_log(settings.db_path, task.id, Stage.VERIFY, verify_result)
    if not verify_result.get("passed"):
        raise RuntimeError(f"verify failed: {verify_result}")

    # PR
    task = _mark(settings, task, stage=Stage.PR)
    pr_result = pr_stage.run(task, wt_path, branch_name, settings)
    task.pr_url = pr_result["pr_url"]
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
    return processed
