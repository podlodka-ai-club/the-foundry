from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from foundry import pipeline, state
from foundry.config import Settings
from foundry.events import read_events
from foundry.models import Stage, Task, TaskStatus


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


def test_run_once_happy_path(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)

    with patch("foundry.pipeline.fetch_stage.fetch", return_value=[seeded]), \
         patch("foundry.workflows.worktree.ensure_base_repo", return_value=tmp_path / "base"), \
         patch(
             "foundry.workflows.worktree.create_worktree",
             return_value=(tmp_path / "wt", "foundry/task-1"),
         ), \
         patch("foundry.workflows.worktree.cleanup_worktree"), \
         patch("foundry.workflows.agent_plan_stage.run", return_value={"plan": "", "summary": ""}), \
         patch("foundry.workflows.agent_implement_stage.run", return_value={"applied": []}), \
         patch("foundry.workflows.verify_stage.run", return_value={"passed": True}), \
         patch(
             "foundry.workflows.pr_stage.run",
             return_value={"pr_url": "https://example/pr/1", "branch": "foundry/task-1"},
         ):
        processed = pipeline.run_once(settings)

    assert len(processed) == 1
    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.DONE
    assert final.current_stage == Stage.DONE
    assert final.pr_url == "https://example/pr/1"

    # Every per-task stage must frame its work with stage_started → stage_finished.
    events = read_events(settings.db_path, task_id=final.id)
    per_stage_kinds: dict[str, list[str]] = {}
    for ev in events:
        per_stage_kinds.setdefault(ev.stage, []).append(ev.kind)
    for stage_name in ("fetch", "context", "plan", "implement", "verify", "pr"):
        assert stage_name in per_stage_kinds, f"no events for stage {stage_name}"
        assert per_stage_kinds[stage_name][0] == "stage_started"
        assert per_stage_kinds[stage_name][-1] == "stage_finished"


def test_fetch_events_are_not_duplicated_on_rerun(tmp_path: Path) -> None:
    """A reset+rerun should not emit a second pair of fetch started/finished events."""
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)

    patches = {
        "foundry.pipeline.fetch_stage.fetch": {"return_value": [seeded]},
        "foundry.workflows.worktree.ensure_base_repo": {"return_value": tmp_path / "base"},
        "foundry.workflows.worktree.create_worktree": {
            "return_value": (tmp_path / "wt", "foundry/task-1"),
        },
        "foundry.workflows.worktree.cleanup_worktree": {},
        "foundry.workflows.agent_plan_stage.run": {"return_value": {"plan": "", "summary": ""}},
        "foundry.workflows.agent_implement_stage.run": {"return_value": {"applied": []}},
        "foundry.workflows.verify_stage.run": {"return_value": {"passed": True}},
        "foundry.workflows.pr_stage.run": {
            "return_value": {"pr_url": "https://example/pr/1", "branch": "foundry/task-1"},
        },
    }

    def _run() -> None:
        ctxs = [patch(target, **kwargs) for target, kwargs in patches.items()]
        for ctx in ctxs:
            ctx.start()
        try:
            pipeline.run_once(settings)
        finally:
            for ctx in ctxs:
                ctx.stop()

    _run()
    task_id = state.list_tasks(settings.db_path)[0].id
    # Simulate a reset: drop pr_url so the task isn't skipped, then rerun.
    task = state.get_task(settings.db_path, task_id)
    task.pr_url = None
    task.status = TaskStatus.PENDING
    task.current_stage = Stage.FETCH
    state.upsert_task(settings.db_path, task)
    _run()

    events = read_events(settings.db_path, task_id=task_id)
    fetch_started = [e for e in events if e.stage == "fetch" and e.kind == "stage_started"]
    fetch_finished = [e for e in events if e.stage == "fetch" and e.kind == "stage_finished"]
    assert len(fetch_started) == 1
    assert len(fetch_finished) == 1


def test_run_once_pre_implement_failure_requeues(tmp_path: Path) -> None:
    """Network/infra flakes before implement should re-queue, not terminally fail."""
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)

    with patch("foundry.pipeline.fetch_stage.fetch", return_value=[seeded]), \
         patch(
             "foundry.workflows.worktree.ensure_base_repo",
             side_effect=RuntimeError("TLS handshake timeout"),
         ):
        processed = pipeline.run_once(settings)

    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.PENDING
    assert final.current_stage == Stage.FETCH
    assert final.attempts == 1


def test_run_once_stage_failure_marks_failed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)

    with patch("foundry.pipeline.fetch_stage.fetch", return_value=[seeded]), \
         patch("foundry.workflows.worktree.ensure_base_repo", return_value=tmp_path / "base"), \
         patch(
             "foundry.workflows.worktree.create_worktree",
             return_value=(tmp_path / "wt", "foundry/task-1"),
         ), \
         patch("foundry.workflows.worktree.cleanup_worktree"), \
         patch("foundry.workflows.agent_plan_stage.run", return_value={"plan": "", "summary": ""}), \
         patch("foundry.workflows.agent_implement_stage.run", side_effect=RuntimeError("boom")):
        processed = pipeline.run_once(settings)

    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.FAILED
    assert final.current_stage == Stage.FAILED
    assert final.pr_url is None

    # The failing stage must have emitted stage_failed (and not stage_finished).
    events = read_events(settings.db_path, task_id=final.id)
    implement_kinds = [e.kind for e in events if e.stage == "implement"]
    assert "stage_started" in implement_kinds
    assert "stage_failed" in implement_kinds
    assert "stage_finished" not in implement_kinds
