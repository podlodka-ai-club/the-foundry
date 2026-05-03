from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from foundry import pipeline, state, workflows
from foundry.config import Settings
from foundry.events import read_events
from foundry.models import Stage, Task, TaskStatus
from foundry.workflows import (
    VerificationDecision,
    WorkflowName,
    needs_human_input,
    normalize_planner_outcome,
    normalize_verification,
    pr_verify,
    strip_human_input_marker,
)


def _settings(tmp_path: Path, *, max_implement_attempts: int = 2) -> Settings:
    return Settings(
        source_repo="owner/sandbox",
        target_repo="owner/sandbox",
        issue_label="agent-task",
        worktree_root=tmp_path / "worktrees",
        db_path=tmp_path / "foundry.sqlite",
        poll_interval_seconds=30,
        max_implement_attempts=max_implement_attempts,
    )


def _seed_task(db_path: Path) -> Task:
    task = Task(
        repo="owner/sandbox",
        issue_number=42,
        issue_title="do the thing",
        issue_body="please",
    )
    return state.upsert_task(db_path, task)


# ----- normalize_verification ---------------------------------------------


def test_normalize_verification_passes_through_passed() -> None:
    decision = normalize_verification({"passed": True, "report": "all green"})

    assert decision.passed is True
    assert decision.retryable is False
    assert decision.requires_human is False
    assert decision.failure_kind is None
    assert decision.report == "all green"


def test_normalize_verification_retryable_failure_is_not_human() -> None:
    decision = normalize_verification(
        {"passed": False, "retryable": True, "failure_kind": "acceptance", "report": "fix me"}
    )

    assert decision.passed is False
    assert decision.retryable is True
    assert decision.requires_human is False
    assert decision.failure_kind == "acceptance"


def test_normalize_verification_unknown_shape_is_conservative() -> None:
    # Unknown failure kinds must not be retried automatically and must surface a human.
    decision = normalize_verification({"passed": False})

    assert decision.passed is False
    assert decision.retryable is False
    assert decision.requires_human is True
    assert decision.failure_kind == "unclear"


def test_normalize_verification_requires_human_blocks_retry() -> None:
    decision = normalize_verification(
        {"passed": False, "retryable": True, "requires_human": True, "failure_kind": "dangerous"}
    )

    assert decision.retryable is False
    assert decision.requires_human is True


# ----- normalize_planner_outcome ------------------------------------------


def test_normalize_planner_outcome_allowlists_known_names() -> None:
    for name in ("plan_ready", "needs_input", "declined", "decompose"):
        assert normalize_planner_outcome(name) == name


def test_normalize_planner_outcome_defaults_unknown_to_plan_ready() -> None:
    # Unknown agent-proposed outcomes must not execute arbitrary branches.
    assert normalize_planner_outcome("launch_nukes") == "plan_ready"
    assert normalize_planner_outcome(None) == "plan_ready"


def test_need_verification_marker_must_be_terminal() -> None:
    assert needs_human_input("Question?\n\nNEED_VERIFICATION") is True
    assert needs_human_input("NEED_VERIFICATION\nextra") is False
    assert strip_human_input_marker("Question?\nNEED_VERIFICATION\n") == "Question?"


# ----- dev_task retry loop ------------------------------------------------


def _dev_task_patches(tmp_path: Path) -> dict[str, dict]:
    return {
        "foundry.workflows.worktree.ensure_base_repo": {"return_value": tmp_path / "base"},
        "foundry.workflows.worktree.create_worktree": {
            "return_value": (tmp_path / "wt", "foundry/task-1"),
        },
        "foundry.workflows.worktree.cleanup_worktree": {},
        "foundry.workflows.agent_plan_stage.run": {
            "return_value": {"plan": "do X", "summary": "plan"}
        },
        "foundry.workflows.pr_stage.run": {
            "return_value": {"pr_url": "https://example/pr/1", "branch": "foundry/task-1"},
        },
    }


def _start(ctxs: list) -> None:
    for c in ctxs:
        c.start()


def _stop(ctxs: list) -> None:
    for c in ctxs:
        c.stop()


def test_dev_task_pass_after_retry_opens_pr(tmp_path: Path) -> None:
    """First attempt fails retryably; second attempt passes → PR is opened."""
    settings = _settings(tmp_path, max_implement_attempts=3)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)

    implement_calls: list[dict] = []

    def _implement_run(task, plan, worktree_path, settings):
        implement_calls.append(plan)
        return {"result": f"attempt-{len(implement_calls)}", "response": ""}

    verify_results = iter([
        {"passed": False, "retryable": True, "failure_kind": "acceptance", "report": "missing file"},
        {"passed": True, "report": "green"},
    ])

    ctxs = [
        patch("foundry.pipeline.fetch_stage.fetch", return_value=[seeded]),
        *[patch(target, **kwargs) for target, kwargs in _dev_task_patches(tmp_path).items()],
        patch("foundry.workflows.agent_implement_stage.run", side_effect=_implement_run),
        patch("foundry.workflows.verify_stage.run", side_effect=lambda *a, **kw: next(verify_results)),
    ]
    _start(ctxs)
    try:
        processed = pipeline.run_once(settings)
    finally:
        _stop(ctxs)

    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.DONE
    assert final.pr_url == "https://example/pr/1"

    # Implement was called twice; second call received the prior verification report.
    assert len(implement_calls) == 2
    assert "missing file" in implement_calls[1]["plan"]

    # Events should show two implement spans with attempt numbers and two verify spans.
    events = read_events(settings.db_path, task_id=final.id)
    implement_started = [
        e for e in events if e.stage == "implement" and e.kind == "stage_started"
    ]
    verify_finished = [
        e for e in events if e.stage == "verify" and e.kind == "stage_finished"
    ]
    assert [e.payload["input"]["attempt"] for e in implement_started] == [1, 2]
    assert [e.payload["output"]["attempt"] for e in verify_finished] == [1, 2]
    assert verify_finished[-1].payload["output"]["passed"] is True


def test_dev_task_resumes_verify_after_process_dies_post_implement(
    tmp_path: Path,
) -> None:
    """A saved IMPLEMENT result lets the next process continue at VERIFY/PR."""
    settings = _settings(tmp_path, max_implement_attempts=2)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)

    real_save_stage_result = state.save_stage_result
    implement_calls: list[dict] = []

    def _implement_run(task, plan, worktree_path, settings):
        implement_calls.append(plan)
        return {"result": "implemented", "response": "implemented"}

    def _crash_after_implement(db_path, task_id, stage, output, *, attempt=0):
        real_save_stage_result(db_path, task_id, stage, output, attempt=attempt)
        if stage == Stage.IMPLEMENT:
            raise SystemExit("simulated process death")

    first_ctxs = [
        *[patch(target, **kwargs) for target, kwargs in _dev_task_patches(tmp_path).items()],
        patch("foundry.workflows.agent_implement_stage.run", side_effect=_implement_run),
        patch(
            "foundry.workflows.state.save_stage_result",
            side_effect=_crash_after_implement,
        ),
    ]
    _start(first_ctxs)
    try:
        try:
            workflows.dev_task(settings, seeded)
        except SystemExit:
            pass
    finally:
        _stop(first_ctxs)

    interrupted = state.get_task(settings.db_path, seeded.id)
    assert interrupted.current_stage == Stage.IMPLEMENT
    assert state.get_stage_result(
        settings.db_path, seeded.id, Stage.IMPLEMENT, attempt=1
    ) == {"result": "implemented", "response": "implemented"}

    verify_calls: list[dict] = []

    def _verify_run(task, worktree_path, settings, impl_result=None):
        verify_calls.append(impl_result)
        return {"passed": True, "report": "green"}

    second_ctxs = [
        patch("foundry.pipeline.fetch_stage.fetch", return_value=[interrupted]),
        *[patch(target, **kwargs) for target, kwargs in _dev_task_patches(tmp_path).items()],
        patch("foundry.workflows.agent_implement_stage.run", side_effect=AssertionError),
        patch("foundry.workflows.verify_stage.run", side_effect=_verify_run),
    ]
    _start(second_ctxs)
    try:
        processed = pipeline.run_once(settings)
    finally:
        _stop(second_ctxs)

    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.DONE
    assert final.current_stage == Stage.DONE
    assert final.pr_url == "https://example/pr/1"
    assert len(implement_calls) == 1
    assert implement_calls[0]["plan"] == "do X"
    assert verify_calls == [{"result": "implemented", "response": "implemented"}]


def test_dev_task_exhausted_retries_marks_failed(tmp_path: Path) -> None:
    """Verifier keeps returning retryable failure → task ends FAILED, no PR."""
    settings = _settings(tmp_path, max_implement_attempts=2)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)

    pr_called = []
    ctxs = [
        patch("foundry.pipeline.fetch_stage.fetch", return_value=[seeded]),
        *[patch(target, **kwargs) for target, kwargs in _dev_task_patches(tmp_path).items()],
        patch("foundry.workflows.agent_implement_stage.run", return_value={"result": "r", "response": ""}),
        patch(
            "foundry.workflows.verify_stage.run",
            return_value={"passed": False, "retryable": True, "failure_kind": "acceptance", "report": "nope"},
        ),
    ]
    # Fail loudly if PR stage is reached.
    pr_patch = patch(
        "foundry.workflows.pr_stage.run",
        side_effect=lambda *a, **kw: pr_called.append(True) or {"pr_url": "bad", "branch": "bad"},
    )
    ctxs.append(pr_patch)
    _start(ctxs)
    try:
        processed = pipeline.run_once(settings)
    finally:
        _stop(ctxs)

    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.FAILED
    assert final.current_stage == Stage.FAILED
    assert final.pr_url is None
    assert pr_called == []

    events = read_events(settings.db_path, task_id=final.id)
    implement_starts = [e for e in events if e.stage == "implement" and e.kind == "stage_started"]
    assert len(implement_starts) == 2  # max_implement_attempts


def test_dev_task_human_blocked_stops_after_one_attempt(tmp_path: Path) -> None:
    """requires_human=True → no second attempt, task BLOCKED, no PR."""
    settings = _settings(tmp_path, max_implement_attempts=5)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)
    comments: list[str] = []

    ctxs = [
        patch("foundry.pipeline.fetch_stage.fetch", return_value=[seeded]),
        *[patch(target, **kwargs) for target, kwargs in _dev_task_patches(tmp_path).items()],
        patch("foundry.workflows.agent_implement_stage.run", return_value={"result": "r", "response": ""}),
        patch(
            "foundry.workflows.verify_stage.run",
            return_value={
                "passed": False,
                "requires_human": True,
                "failure_kind": "dangerous",
                "report": "rm -rf /",
            },
        ),
        patch(
            "foundry.workflows.issue_comment_stage.run",
            side_effect=lambda task, settings, body, cwd=None: comments.append(body)
            or {"issue_number": task.issue_number, "comment": body},
        ),
        patch("foundry.workflows.pr_stage.run"),
    ]
    _start(ctxs)
    try:
        processed = pipeline.run_once(settings)
    finally:
        _stop(ctxs)

    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.BLOCKED
    assert final.current_stage == Stage.VERIFY
    assert final.pr_url is None
    assert "rm -rf /" in comments[0]

    events = read_events(settings.db_path, task_id=final.id)
    implement_starts = [e for e in events if e.stage == "implement" and e.kind == "stage_started"]
    assert len(implement_starts) == 1


def test_dev_task_unclear_plan_comments_and_blocks(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)
    comments: list[str] = []

    ctxs = [
        patch("foundry.pipeline.fetch_stage.fetch", return_value=[seeded]),
        patch("foundry.workflows.worktree.ensure_base_repo", return_value=tmp_path / "base"),
        patch(
            "foundry.workflows.worktree.create_worktree",
            return_value=(tmp_path / "wt", "foundry/task-1"),
        ),
        patch("foundry.workflows.worktree.cleanup_worktree"),
        patch(
            "foundry.workflows.agent_plan_stage.run",
            return_value={
                "plan": "Please clarify the desired API shape.\nNEED_VERIFICATION",
                "summary": "needs input",
            },
        ),
        patch(
            "foundry.workflows.agent_implement_stage.run",
            side_effect=AssertionError("implement should not run"),
        ),
        patch(
            "foundry.workflows.issue_comment_stage.run",
            side_effect=lambda task, settings, body, cwd=None: comments.append(body)
            or {"issue_number": task.issue_number, "comment": body},
        ),
        patch(
            "foundry.workflows.pr_stage.run",
            side_effect=AssertionError("pr should not run"),
        ),
    ]
    _start(ctxs)
    try:
        processed = pipeline.run_once(settings)
    finally:
        _stop(ctxs)

    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.BLOCKED
    assert final.current_stage == Stage.PLAN
    assert final.pr_url is None
    assert comments
    assert "Please clarify the desired API shape." in comments[0]
    assert "NEED_VERIFICATION" not in comments[0]


def test_dev_task_unclear_implement_comments_and_blocks(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)
    comments: list[str] = []

    ctxs = [
        patch("foundry.pipeline.fetch_stage.fetch", return_value=[seeded]),
        *[patch(target, **kwargs) for target, kwargs in _dev_task_patches(tmp_path).items()],
        patch(
            "foundry.workflows.agent_implement_stage.run",
            return_value={
                "result": "needs input",
                "response": "Which auth scope should this endpoint use?\nNEED_VERIFICATION",
            },
        ),
        patch(
            "foundry.workflows.verify_stage.run",
            side_effect=AssertionError("verify should not run"),
        ),
        patch(
            "foundry.workflows.issue_comment_stage.run",
            side_effect=lambda task, settings, body, cwd=None: comments.append(body)
            or {"issue_number": task.issue_number, "comment": body},
        ),
    ]
    _start(ctxs)
    try:
        processed = pipeline.run_once(settings)
    finally:
        _stop(ctxs)

    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.BLOCKED
    assert final.current_stage == Stage.IMPLEMENT
    assert final.pr_url is None
    assert "Which auth scope should this endpoint use?" in comments[0]
    assert "NEED_VERIFICATION" not in comments[0]


# ----- pr_verify workflow -------------------------------------------------


def test_pr_verify_passed_returns_report_and_skips_pr(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)

    with patch(
        "foundry.workflows.verify_stage.run",
        return_value={"passed": True, "report": "all green"},
    ), patch("foundry.workflows.pr_stage.run") as pr_mock:
        decision = pr_verify(settings, seeded, tmp_path / "wt")

    assert decision.passed is True
    assert decision.report == "all green"
    pr_mock.assert_not_called()

    # Task must NOT be marked done or get a PR url.
    final = state.get_task(settings.db_path, seeded.id)
    assert final.status != TaskStatus.DONE
    assert final.pr_url is None

    events = read_events(settings.db_path, task_id=seeded.id)
    verify_events = [e for e in events if e.stage == "verify"]
    assert [e.kind for e in verify_events] == ["stage_started", "stage_finished"]
    assert verify_events[0].payload["input"]["workflow"] == WorkflowName.PR_VERIFY.value
    assert verify_events[-1].payload["output"]["passed"] is True


def test_pr_verify_failed_returns_failure_report(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)

    raw = {
        "passed": False,
        "retryable": True,
        "failure_kind": "acceptance",
        "report": "test X failed",
    }
    with patch("foundry.workflows.verify_stage.run", return_value=raw), patch(
        "foundry.workflows.pr_stage.run"
    ) as pr_mock:
        decision = pr_verify(settings, seeded, tmp_path / "wt")

    assert decision.passed is False
    assert decision.retryable is True
    assert decision.failure_kind == "acceptance"
    assert "test X failed" in decision.report
    pr_mock.assert_not_called()

    final = state.get_task(settings.db_path, seeded.id)
    # pr_verify never opens PRs and never closes the source issue.
    assert final.pr_url is None
    assert final.status != TaskStatus.DONE


def test_verification_decision_is_frozen() -> None:
    # Smoke-check the dataclass contract so future refactors don't silently break it.
    decision = VerificationDecision(
        passed=True, retryable=False, requires_human=False, failure_kind=None, report="ok"
    )
    try:
        decision.passed = False  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("VerificationDecision should be frozen")


def test_workflows_module_exposes_public_names() -> None:
    # Guardrail: if any of these disappear, downstream callers break silently.
    assert workflows.WorkflowName.DEV_TASK.value == "dev_task"
    assert workflows.WorkflowName.PR_VERIFY.value == "pr_verify"
    assert workflows.WorkflowName.PR_FEEDBACK.value == "pr_feedback"
    assert hasattr(workflows, "dev_task")
    assert hasattr(workflows, "pr_verify")
    assert hasattr(workflows, "pr_feedback_once")
    assert hasattr(workflows, "normalize_verification")
    assert hasattr(workflows, "normalize_planner_outcome")
