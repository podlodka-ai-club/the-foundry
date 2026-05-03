"""Workflow orchestration layer.

Named workflows sit between `pipeline.run_once` (fetch + batch loop) and the
stage functions. Each workflow is a plain Python helper that drives existing
stages, emits `task_events`, and persists task state — without introducing a
second state runtime alongside SQLite/events.

Defined workflows:
- `dev_task`: full issue → context → plan → implement(loop) → verify → PR cycle.
- `pr_verify`: verification-only entrypoint against an existing worktree context.

Planner outcomes (`plan_ready`, `needs_input`, `declined`, `decompose`) are
future-facing: the orchestrator only executes the allowlisted transition and
refuses to run agent-defined branches.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import structlog
from langfuse import observe

from . import security, shell, state, worktree
from .agents import AgentSettings, AgentStage
from .agents.base import AgentTask, build_fresh_prompt
from .config import Settings
from .events import read_events, record_event, stage_span
from .models import Stage, Task, TaskStatus
from .stages import agent_implement as agent_implement_stage
from .stages import agent_plan as agent_plan_stage
from .stages import context as context_stage
from .stages import issue_comment as issue_comment_stage
from .stages import pr as pr_stage
from .stages import verify as verify_stage

log = structlog.get_logger()


class WorkflowName(str, Enum):
    DEV_TASK = "dev_task"
    PR_VERIFY = "pr_verify"
    PR_FEEDBACK = "pr_feedback"


FailureKind = Literal["deterministic", "acceptance", "infra", "unclear", "dangerous"]


@dataclass(frozen=True)
class VerificationDecision:
    """Normalized verifier output consumed by the workflow."""

    passed: bool
    retryable: bool
    requires_human: bool
    failure_kind: FailureKind | None
    report: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepResult:
    """Outcome of a single workflow step."""

    stage: Stage
    ok: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


ALLOWED_PLANNER_OUTCOMES: frozenset[str] = frozenset(
    {"plan_ready", "needs_input", "declined", "decompose"}
)
PlannerOutcome = Literal["plan_ready", "needs_input", "declined", "decompose"]
NEED_VERIFICATION = "NEED_VERIFICATION"


def normalize_planner_outcome(outcome: str | None) -> PlannerOutcome:
    """Map a planner's proposed outcome to an allowlisted name.

    Unknown values collapse to `plan_ready` so the orchestrator never executes
    an agent-defined branch it wasn't designed for.
    """
    if outcome in ALLOWED_PLANNER_OUTCOMES:
        return outcome  # type: ignore[return-value]
    return "plan_ready"


def needs_human_input(text: str | None) -> bool:
    """Return True when the last non-empty agent output line asks for a human."""
    if not text:
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return bool(lines) and lines[-1] == NEED_VERIFICATION


def strip_human_input_marker(text: str | None) -> str:
    """Remove the terminal NEED_VERIFICATION marker from a human-facing comment."""
    if not text:
        return ""
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip() == NEED_VERIFICATION:
        lines.pop()
    return "\n".join(lines).strip()


def normalize_verification(raw: dict[str, Any]) -> VerificationDecision:
    """Normalize a raw verifier dict into a typed decision.

    Conservative defaults: if the verifier reports failure with an unrecognised
    shape, treat it as `unclear` + `requires_human` so the workflow stops
    instead of looping on an output it cannot interpret.
    """
    passed = bool(raw.get("passed", False))
    report = str(raw.get("report") or raw.get("stdout") or "")
    if passed:
        return VerificationDecision(
            passed=True,
            retryable=False,
            requires_human=False,
            failure_kind=None,
            report=report,
            raw=raw,
        )
    failure_kind = raw.get("failure_kind")
    if failure_kind not in ("deterministic", "acceptance", "infra", "dangerous"):
        failure_kind = "unclear"
    requires_human = bool(raw.get("requires_human")) or failure_kind == "unclear"
    retryable = bool(raw.get("retryable")) and not requires_human
    return VerificationDecision(
        passed=False,
        retryable=retryable,
        requires_human=requires_human,
        failure_kind=failure_kind,
        report=report,
        raw=raw,
    )


def _mark(
    settings: Settings, task: Task, *, stage: Stage, status: TaskStatus | None = None
) -> Task:
    task.current_stage = stage
    if status is not None:
        task.status = status
    return state.upsert_task(settings.db_path, task)


def _emit_synthetic_fetch_events(settings: Settings, task: Task) -> None:
    """Emit fetch stage_started/finished for issue-driven tasks.

    `fetch` runs as a batch before the workflow, so there is no stage_span
    wrapping it. Idempotent: if a stage_finished already exists, skip.
    """
    existing = read_events(settings.db_path, task_id=task.id)
    has_finished = any(
        e.stage == Stage.FETCH.value and e.kind == "stage_finished" for e in existing
    )
    if has_finished:
        return
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


def _build_attempt_input(
    plan_text: str,
    attempt: int,
    previous_summary: str = "",
    previous_report: str = "",
) -> str:
    """Augment implement input on retry with prior attempt + verifier feedback."""
    if attempt == 1:
        return plan_text
    parts = [plan_text, f"\n\n## Attempt {attempt} — previous feedback\n"]
    if previous_summary:
        parts.append(f"\n### Previous implement summary\n{previous_summary}\n")
    if previous_report:
        parts.append(f"\n### Previous verification report\n{previous_report}\n")
    return "".join(parts)


def _build_pr_feedback_input(pr: dict[str, Any], feedback: str) -> str:
    return "\n".join(
        [
            "Address the latest PR feedback on the existing branch.",
            "",
            f"PR: #{pr.get('number')} {pr.get('title', '')}".strip(),
            f"Branch: `{pr.get('headRefName', '')}`",
            f"URL: {pr.get('url', '')}",
            "",
            "## Feedback",
            feedback.strip(),
            "",
            "Make the minimal code changes needed to satisfy this feedback. "
            "Do not open a new PR, switch branches, commit, or push.",
        ]
    )


def _has_failing_check(check: dict[str, Any]) -> bool:
    conclusion = str(check.get("conclusion") or "").upper()
    status = str(check.get("status") or check.get("state") or "").upper()
    if conclusion in {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}:
        return True
    return status in {"FAILURE", "ERROR", "FAILED"}


def _format_pr_feedback(pr: dict[str, Any]) -> str:
    parts: list[str] = []

    requested = []
    for review in pr.get("reviews", []):
        if str(review.get("state", "")).upper() == "CHANGES_REQUESTED":
            requested.append(review)
    if requested:
        lines = ["### Requested changes"]
        for review in requested:
            author = (review.get("author") or {}).get("login") or "unknown"
            body = (review.get("body") or "").strip()
            lines.append(f"- {author}: {body or 'requested changes'}")
        parts.append("\n".join(lines))

    failing = []
    for check in pr.get("statusCheckRollup", []):
        if isinstance(check, dict) and _has_failing_check(check):
            failing.append(check)
    if failing:
        lines = ["### Failing CI"]
        for check in failing:
            name = (
                check.get("name")
                or check.get("context")
                or check.get("workflowName")
                or "check"
            )
            state = (
                check.get("conclusion")
                or check.get("status")
                or check.get("state")
                or "failed"
            )
            lines.append(f"- {name}: {state}")
        parts.append("\n".join(lines))

    comments = [
        c.get("body", "").strip()
        for c in pr.get("comments", [])
        if isinstance(c, dict) and c.get("body", "").strip()
    ]
    if comments and (requested or failing):
        parts.append("### PR comments\n" + "\n\n".join(comments[-5:]))

    return "\n\n".join(parts).strip()


def _list_open_foundry_prs(settings: Settings) -> list[dict[str, Any]]:
    result = shell.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            settings.target_repo,
            "--state",
            "open",
            "--json",
            "number,title,headRefName,url",
            "--limit",
            "100",
        ]
    )
    prs = json.loads(result.stdout or "[]")
    return [
        pr
        for pr in prs
        if str(pr.get("headRefName") or "").startswith("foundry/task-")
    ]


def _view_pr_feedback(settings: Settings, pr_number: int) -> dict[str, Any]:
    result = shell.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            settings.target_repo,
            "--json",
            "number,title,headRefName,url,reviews,comments,statusCheckRollup",
        ]
    )
    return json.loads(result.stdout or "{}")


def _task_for_pr(settings: Settings, pr: dict[str, Any]) -> Task | None:
    branch = str(pr.get("headRefName") or "")
    for task in state.list_tasks(settings.db_path):
        if task.branch_name == branch or task.pr_url == pr.get("url"):
            return task

    prefix = "foundry/task-"
    if branch.startswith(prefix):
        try:
            return state.get_task(settings.db_path, int(branch.removeprefix(prefix)))
        except ValueError:
            return None
    return None


def _prepare_pr_feedback_worktree(
    settings: Settings, task: Task, branch_name: str
) -> tuple[Path, Path]:
    base = worktree.ensure_base_repo(settings.worktree_root, settings.source_repo)
    wt_path = (settings.worktree_root / f"task-{task.id}-pr-feedback").resolve()
    if wt_path.exists():
        worktree.cleanup_worktree(base, wt_path)
    shell.run(["git", "branch", "-D", branch_name], cwd=base, check=False)
    shell.run(["git", "fetch", "origin", branch_name], cwd=base)
    shell.run(
        [
            "git",
            "worktree",
            "add",
            str(wt_path),
            "-B",
            branch_name,
            f"origin/{branch_name}",
        ],
        cwd=base,
    )
    return base, wt_path


def _block_for_human(
    settings: Settings,
    task: Task,
    *,
    blocked_stage: Stage,
    reason: str,
    questions: str,
    worktree_path: Path | None,
) -> Task:
    comment = "\n".join(
        part
        for part in [
            "The Foundry needs human input before continuing this task.",
            "",
            f"Blocked at stage: `{blocked_stage.value}`.",
            "",
            questions.strip() or reason,
        ]
        if part
    )
    with stage_span(
        settings.db_path,
        task.id,
        Stage.ISSUE_COMMENT.value,
        input={"blocked_stage": blocked_stage.value},
    ) as finish:
        result = issue_comment_stage.run(
            task, settings, comment, cwd=worktree_path
        )
        finish(output={"issue_number": task.issue_number})
    state.append_log(
        settings.db_path,
        task.id,
        Stage.ISSUE_COMMENT,
        {"blocked_stage": blocked_stage.value, "reason": reason, **result},
    )
    task.current_stage = blocked_stage
    task.status = TaskStatus.BLOCKED
    return state.upsert_task(settings.db_path, task)


@observe(name="workflow.dev_task")
def dev_task(settings: Settings, task: Task) -> Task:
    """Issue-driven development workflow.

    Flow: context → plan → (implement → verify) × up to N attempts → pr.
    The orchestrator — not the agent or verifier — picks transitions on each
    verification result. Terminal failures (requires_human, non-retryable,
    exhausted budget) propagate as exceptions; `pipeline.run_once` translates
    them into task status per `PRE_IMPLEMENT_STAGES` policy.
    """
    log.info("workflow.dev_task.start", task_id=task.id, issue=task.issue_number)

    if task.pr_url:
        log.info("task.skip_already_has_pr", task_id=task.id, pr_url=task.pr_url)
        return task

    if task.id is None:
        task = state.upsert_task(settings.db_path, task)

    task.attempts += 1
    task.status = TaskStatus.RUNNING
    task = state.upsert_task(settings.db_path, task)

    _emit_synthetic_fetch_events(settings, task)

    base = worktree.ensure_base_repo(settings.worktree_root, settings.source_repo)
    if task.worktree_path and task.branch_name:
        wt_path = Path(task.worktree_path)
        branch_name = task.branch_name
    else:
        wt_path, branch_name = worktree.create_worktree(settings.worktree_root, task.id)
        task.worktree_path = str(wt_path)
        task.branch_name = branch_name
        task = state.upsert_task(settings.db_path, task)

    # CONTEXT
    ctx = state.get_stage_result(settings.db_path, task.id, Stage.CONTEXT)
    if ctx is None:
        task = _mark(settings, task, stage=Stage.CONTEXT)
        with stage_span(settings.db_path, task.id, Stage.CONTEXT.value) as finish:
            ctx = context_stage.run(task, settings, repo_path=wt_path)
            finish(output=ctx)
        state.save_stage_result(settings.db_path, task.id, Stage.CONTEXT, ctx)
        state.append_log(settings.db_path, task.id, Stage.CONTEXT, {"ok": True})

    # PLAN
    plan = state.get_stage_result(settings.db_path, task.id, Stage.PLAN)
    if plan is None:
        task = _mark(settings, task, stage=Stage.PLAN)
        plan_agent_settings = AgentSettings.from_env(
            AgentStage.PLAN, db_path=settings.db_path
        )
        plan_agent_task = AgentTask(
            id=task.id or task.issue_number,
            title=task.issue_title,
            description=task.issue_body,
        )
        plan_input = context_stage.format_for_prompt(ctx)
        plan_prompt = build_fresh_prompt(AgentStage.PLAN, plan_agent_task, plan_input)
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
        state.save_stage_result(settings.db_path, task.id, Stage.PLAN, plan)
        state.append_log(
            settings.db_path, task.id, Stage.PLAN, {"summary": plan.get("summary", "")}
        )
    plan_text = plan.get("plan", "")
    if needs_human_input(plan_text):
        return _block_for_human(
            settings,
            task,
            blocked_stage=Stage.PLAN,
            reason="plan requested human verification",
            questions=strip_human_input_marker(plan_text),
            worktree_path=wt_path,
        )

    # IMPLEMENT → VERIFY quality-gate loop
    max_attempts = max(1, settings.max_implement_attempts)
    latest_impl = state.get_latest_stage_result(settings.db_path, task.id, Stage.IMPLEMENT)
    latest_verify = state.get_latest_stage_result(settings.db_path, task.id, Stage.VERIFY)
    impl_result: dict[str, Any] = latest_impl[1] if latest_impl else {}
    decision = VerificationDecision(
        passed=False,
        retryable=False,
        requires_human=False,
        failure_kind=None,
        report="",
        raw={},
    )
    if latest_verify:
        decision = normalize_verification(latest_verify[1])
    for attempt in range(1, max_attempts + 1):
        attempt_plan = dict(plan)
        attempt_plan["plan"] = _build_attempt_input(
            plan_text,
            attempt,
            previous_summary=impl_result.get("result", "") if attempt > 1 else "",
            previous_report=decision.report if attempt > 1 else "",
        )

        saved_impl = state.get_stage_result(
            settings.db_path, task.id, Stage.IMPLEMENT, attempt=attempt
        )
        if saved_impl is None:
            checkpoint_path = security.checkpoint_diff(
                worktree_path=wt_path,
                checkpoint_root=settings.db_path.parent / "checkpoints",
                task_id=task.id or task.issue_number,
                attempt=attempt,
            )
            state.append_log(
                settings.db_path,
                task.id,
                Stage.IMPLEMENT,
                {"attempt": attempt, "checkpoint": str(checkpoint_path)},
            )
            if attempt > 1:
                security.reset_task_worktree(wt_path, settings.worktree_root)

            task = _mark(settings, task, stage=Stage.IMPLEMENT)
            impl_agent_settings = AgentSettings.from_env(
                AgentStage.IMPLEMENT, db_path=settings.db_path
            )
            impl_agent_task = AgentTask(
                id=task.id or task.issue_number,
                title=task.issue_title,
                description=task.issue_body,
            )
            impl_prompt = build_fresh_prompt(
                AgentStage.IMPLEMENT, impl_agent_task, attempt_plan["plan"]
            )
            with stage_span(
                settings.db_path,
                task.id,
                Stage.IMPLEMENT.value,
                input={
                    "title": task.issue_title,
                    "prompt": impl_prompt,
                    "attempt": attempt,
                },
                agent={
                    "name": impl_agent_settings.backend,
                    "model": impl_agent_settings.model,
                },
            ) as finish:
                impl_result = agent_implement_stage.run(
                    task, attempt_plan, wt_path, settings
                )
                finish(
                    output={
                        "summary": impl_result.get("result", ""),
                        "text": impl_result.get("response", ""),
                        "attempt": attempt,
                    },
                    cost_usd=impl_result.get("cost_usd"),
                    tokens_in=impl_result.get("tokens_in"),
                    tokens_out=impl_result.get("tokens_out"),
                )
            state.save_stage_result(
                settings.db_path, task.id, Stage.IMPLEMENT, impl_result, attempt=attempt
            )
            state.append_log(
                settings.db_path,
                task.id,
                Stage.IMPLEMENT,
                {**impl_result, "attempt": attempt},
            )
        else:
            impl_result = saved_impl
        if needs_human_input(impl_result.get("response") or impl_result.get("result")):
            return _block_for_human(
                settings,
                task,
                blocked_stage=Stage.IMPLEMENT,
                reason=f"implement requested human verification on attempt {attempt}",
                questions=strip_human_input_marker(
                    impl_result.get("response") or impl_result.get("result")
                ),
                worktree_path=wt_path,
            )

        # VERIFY
        saved_verify = state.get_stage_result(
            settings.db_path, task.id, Stage.VERIFY, attempt=attempt
        )
        if saved_verify is None:
            task = _mark(settings, task, stage=Stage.VERIFY)
            with stage_span(
                settings.db_path,
                task.id,
                Stage.VERIFY.value,
                input={"attempt": attempt},
            ) as finish:
                verify_raw = verify_stage.run(
                    task, wt_path, settings, impl_result=impl_result
                )
                decision = normalize_verification(verify_raw)
                finish(
                    output={
                        "passed": decision.passed,
                        "retryable": decision.retryable,
                        "requires_human": decision.requires_human,
                        "failure_kind": decision.failure_kind,
                        "report": decision.report,
                        "attempt": attempt,
                    }
                )
            state.save_stage_result(
                settings.db_path, task.id, Stage.VERIFY, verify_raw, attempt=attempt
            )
            state.append_log(
                settings.db_path,
                task.id,
                Stage.VERIFY,
                {
                    "attempt": attempt,
                    "passed": decision.passed,
                    "retryable": decision.retryable,
                    "requires_human": decision.requires_human,
                    "failure_kind": decision.failure_kind,
                },
            )
        else:
            decision = normalize_verification(saved_verify)

        if decision.passed:
            break
        if decision.requires_human:
            return _block_for_human(
                settings,
                task,
                blocked_stage=Stage.VERIFY,
                reason=(
                    f"verify requires human intervention (attempt {attempt}, "
                    f"kind={decision.failure_kind})"
                ),
                questions=decision.report,
                worktree_path=wt_path,
            )
        if not decision.retryable:
            raise RuntimeError(
                f"verify failed non-retryably (attempt {attempt}, "
                f"kind={decision.failure_kind}): {decision.report}"
            )
        if attempt >= max_attempts:
            raise RuntimeError(
                f"verify failed after {attempt} attempts "
                f"(kind={decision.failure_kind}): {decision.report}"
            )
        # Otherwise: retryable failure with remaining budget — loop.

    # PR
    pr_result = state.get_stage_result(settings.db_path, task.id, Stage.PR)
    if pr_result is None:
        task = _mark(settings, task, stage=Stage.PR)
        with stage_span(settings.db_path, task.id, Stage.PR.value) as finish:
            pr_result = pr_stage.run(
                task, wt_path, branch_name, settings, report=decision.report
            )
            task.pr_url = pr_result["pr_url"]
            finish(output={"pr_url": pr_result["pr_url"]})
        state.save_stage_result(settings.db_path, task.id, Stage.PR, pr_result)
        state.append_log(settings.db_path, task.id, Stage.PR, pr_result)
        _save_successful_pr_memory(settings, task, pr_result, ctx)
    else:
        task.pr_url = pr_result.get("pr_url")

    task = _mark(settings, task, stage=Stage.DONE, status=TaskStatus.DONE)
    worktree.cleanup_worktree(base, wt_path)
    log.info("workflow.dev_task.done", task_id=task.id, pr_url=task.pr_url)
    return task


def _save_successful_pr_memory(
    settings: Settings,
    task: Task,
    pr_result: dict[str, Any],
    ctx: dict[str, Any],
) -> None:
    if task.id is None:
        return

    touched_files = pr_result.get("touched_files") or ctx.get("files") or []
    if touched_files:
        state.save_repo_memory(
            settings.db_path, task.repo, "touched_files", touched_files
        )

    verify_commands = ctx.get("test_commands") or []
    if verify_commands:
        state.save_repo_memory(
            settings.db_path, task.repo, "verify_commands", verify_commands
        )

    common_failures = _common_verify_failures(settings.db_path, task.id)
    if common_failures:
        state.save_repo_memory(
            settings.db_path, task.repo, "common_failures", common_failures
        )


def _common_verify_failures(db_path: Path, task_id: int) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for attempt, output in state.list_stage_results(db_path, task_id, Stage.VERIFY):
        if output.get("passed") is True:
            continue
        report = str(output.get("report") or "").strip()
        failure_kind = str(output.get("failure_kind") or "unknown")
        if not report and output.get("stdout"):
            report = str(output["stdout"]).strip()
        if report:
            failures.append(
                {
                    "attempt": str(attempt),
                    "failure_kind": failure_kind,
                    "report": report[:1000],
                }
            )
    return failures[-5:]


@observe(name="workflow.pr_verify")
def pr_verify(
    settings: Settings,
    task: Task,
    worktree_path: Path,
    impl_result: dict[str, Any] | None = None,
) -> VerificationDecision:
    """PR-facing verification workflow.

    Runs the verify stage against a pre-existing worktree/task context and
    returns the normalized decision. Does NOT commit, push, open a PR, close the
    source issue, or mark the task `DONE` — those are `dev_task`'s job.
    """
    log.info("workflow.pr_verify.start", task_id=task.id)
    task = _mark(settings, task, stage=Stage.VERIFY)
    with stage_span(
        settings.db_path,
        task.id,
        Stage.VERIFY.value,
        input={"workflow": WorkflowName.PR_VERIFY.value},
    ) as finish:
        verify_raw = verify_stage.run(
            task, worktree_path, settings, impl_result=impl_result
        )
        decision = normalize_verification(verify_raw)
        finish(
            output={
                "passed": decision.passed,
                "retryable": decision.retryable,
                "requires_human": decision.requires_human,
                "failure_kind": decision.failure_kind,
                "report": decision.report,
                "workflow": WorkflowName.PR_VERIFY.value,
            }
        )
    state.append_log(
        settings.db_path,
        task.id,
        Stage.VERIFY,
        {
            "workflow": WorkflowName.PR_VERIFY.value,
            "passed": decision.passed,
            "report": decision.report,
        },
    )
    log.info(
        "workflow.pr_verify.done", task_id=task.id, passed=decision.passed
    )
    return decision


@observe(name="workflow.pr_feedback")
def pr_feedback(
    settings: Settings,
    task: Task,
    pr: dict[str, Any],
    feedback: str,
) -> Task:
    """Apply requested PR feedback on the existing PR branch.

    This is intentionally small: it records the external feedback, runs the
    implement agent with that feedback, verifies the result, pushes one commit
    back to the same branch, and posts a PR comment.
    """
    branch_name = str(pr.get("headRefName") or task.branch_name or "")
    if not branch_name:
        raise RuntimeError(f"PR #{pr.get('number')} has no head branch")

    log.info(
        "workflow.pr_feedback.start",
        task_id=task.id,
        pr_number=pr.get("number"),
        branch=branch_name,
    )
    task.branch_name = branch_name
    task.pr_url = str(pr.get("url") or task.pr_url or "")
    task.status = TaskStatus.PENDING
    task.current_stage = Stage.IMPLEMENT
    task = state.upsert_task(settings.db_path, task)
    record_event(
        settings.db_path,
        task.id,
        Stage.IMPLEMENT.value,
        "pr_feedback",
        {
            "workflow": WorkflowName.PR_FEEDBACK.value,
            "status": TaskStatus.PENDING.value,
            "stage": Stage.IMPLEMENT.value,
            "pr_number": pr.get("number"),
            "pr_url": pr.get("url"),
            "branch": branch_name,
            "feedback": feedback,
        },
    )
    state.append_log(
        settings.db_path,
        task.id,
        Stage.IMPLEMENT,
        {
            "workflow": WorkflowName.PR_FEEDBACK.value,
            "pr_number": pr.get("number"),
            "branch": branch_name,
            "feedback": feedback,
        },
    )

    base, wt_path = _prepare_pr_feedback_worktree(settings, task, branch_name)
    task.worktree_path = str(wt_path)
    task.status = TaskStatus.RUNNING
    task = state.upsert_task(settings.db_path, task)

    try:
        implement_input = _build_pr_feedback_input(pr, feedback)
        impl_agent_settings = AgentSettings.from_env(
            AgentStage.IMPLEMENT, db_path=settings.db_path
        )
        impl_agent_task = AgentTask(
            id=task.id or task.issue_number,
            title=task.issue_title,
            description=task.issue_body,
        )
        impl_prompt = build_fresh_prompt(
            AgentStage.IMPLEMENT, impl_agent_task, implement_input
        )
        with stage_span(
            settings.db_path,
            task.id,
            Stage.IMPLEMENT.value,
            input={
                "workflow": WorkflowName.PR_FEEDBACK.value,
                "pr_number": pr.get("number"),
                "prompt": impl_prompt,
            },
            agent={
                "name": impl_agent_settings.backend,
                "model": impl_agent_settings.model,
            },
        ) as finish:
            impl_result = agent_implement_stage.run(
                task, {"plan": implement_input}, wt_path, settings
            )
            finish(
                output={
                    "summary": impl_result.get("result", ""),
                    "text": impl_result.get("response", ""),
                },
                cost_usd=impl_result.get("cost_usd"),
                tokens_in=impl_result.get("tokens_in"),
                tokens_out=impl_result.get("tokens_out"),
            )
        state.append_log(
            settings.db_path,
            task.id,
            Stage.IMPLEMENT,
            {**impl_result, "workflow": WorkflowName.PR_FEEDBACK.value},
        )

        if needs_human_input(impl_result.get("response") or impl_result.get("result")):
            return _block_for_human(
                settings,
                task,
                blocked_stage=Stage.IMPLEMENT,
                reason="implement requested human verification while addressing PR feedback",
                questions=strip_human_input_marker(
                    impl_result.get("response") or impl_result.get("result")
                ),
                worktree_path=wt_path,
            )

        task = _mark(settings, task, stage=Stage.VERIFY)
        with stage_span(
            settings.db_path,
            task.id,
            Stage.VERIFY.value,
            input={
                "workflow": WorkflowName.PR_FEEDBACK.value,
                "pr_number": pr.get("number"),
            },
        ) as finish:
            verify_raw = verify_stage.run(
                task, wt_path, settings, impl_result=impl_result
            )
            decision = normalize_verification(verify_raw)
            finish(
                output={
                    "passed": decision.passed,
                    "retryable": decision.retryable,
                    "requires_human": decision.requires_human,
                    "failure_kind": decision.failure_kind,
                    "report": decision.report,
                    "workflow": WorkflowName.PR_FEEDBACK.value,
                }
            )
        state.append_log(
            settings.db_path,
            task.id,
            Stage.VERIFY,
            {
                "workflow": WorkflowName.PR_FEEDBACK.value,
                "passed": decision.passed,
                "report": decision.report,
            },
        )
        if not decision.passed:
            if decision.requires_human:
                return _block_for_human(
                    settings,
                    task,
                    blocked_stage=Stage.VERIFY,
                    reason="verify requires human intervention after PR feedback fix",
                    questions=decision.report,
                    worktree_path=wt_path,
                )
            raise RuntimeError(
                "PR feedback fix did not pass verification: " + decision.report
            )

        task = _mark(settings, task, stage=Stage.PR)
        commit_message = f"foundry: address PR feedback for task #{task.issue_number}"
        with stage_span(
            settings.db_path,
            task.id,
            Stage.PR.value,
            input={
                "workflow": WorkflowName.PR_FEEDBACK.value,
                "pr_number": pr.get("number"),
            },
        ) as finish:
            push_result = pr_stage.commit_and_push_changes(
                task, wt_path, branch_name, commit_message
            )
            comment = "\n".join(
                [
                    "The Foundry pushed a follow-up commit addressing the latest PR feedback.",
                    "",
                    "## Verification",
                    decision.report.strip() or "Verification passed.",
                ]
            )
            shell.run(
                [
                    "gh",
                    "pr",
                    "comment",
                    str(pr.get("number")),
                    "--repo",
                    settings.target_repo,
                    "--body",
                    comment,
                ],
                cwd=wt_path,
            )
            finish(output={**push_result, "commented": True})
        state.append_log(
            settings.db_path,
            task.id,
            Stage.PR,
            {
                "workflow": WorkflowName.PR_FEEDBACK.value,
                "branch": branch_name,
                "commented": True,
            },
        )

        task = _mark(settings, task, stage=Stage.DONE, status=TaskStatus.DONE)
        log.info(
            "workflow.pr_feedback.done",
            task_id=task.id,
            pr_number=pr.get("number"),
        )
        return task
    finally:
        worktree.cleanup_worktree(base, wt_path)


def pr_feedback_once(settings: Settings) -> list[Task]:
    """Run one PR feedback pass for open `foundry/task-*` PRs."""
    state.init_db(settings.db_path)
    processed: list[Task] = []
    for listed_pr in _list_open_foundry_prs(settings):
        pr = _view_pr_feedback(settings, int(listed_pr["number"]))
        feedback = _format_pr_feedback(pr)
        if not feedback:
            continue
        task = _task_for_pr(settings, pr)
        if task is None:
            log.warning(
                "workflow.pr_feedback.no_task",
                pr_number=pr.get("number"),
                branch=pr.get("headRefName"),
            )
            continue
        processed.append(pr_feedback(settings, task, pr, feedback))
    return processed
