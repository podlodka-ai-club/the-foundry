from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from foundry import pipeline, state
from foundry.config import Settings
from foundry.models import Stage, Task, TaskStatus


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        source_repo="owner/sandbox",
        target_repo="owner/sandbox",
        issue_label="agent-task",
        worktree_root=tmp_path / "worktrees",
        db_path=tmp_path / "foundry.sqlite",
        poll_interval_seconds=30,
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
         patch("foundry.pipeline.worktree.ensure_base_repo", return_value=tmp_path / "base"), \
         patch(
             "foundry.pipeline.worktree.create_worktree",
             return_value=(tmp_path / "wt", "foundry/task-1"),
         ), \
         patch("foundry.pipeline.worktree.cleanup_worktree"), \
         patch("foundry.pipeline.implement_stage.run", return_value={"applied": []}), \
         patch("foundry.pipeline.verify_stage.run", return_value={"passed": True}), \
         patch(
             "foundry.pipeline.pr_stage.run",
             return_value={"pr_url": "https://example/pr/1", "branch": "foundry/task-1"},
         ):
        processed = pipeline.run_once(settings)

    assert len(processed) == 1
    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.DONE
    assert final.current_stage == Stage.DONE
    assert final.pr_url == "https://example/pr/1"


def test_run_once_pre_implement_failure_requeues(tmp_path: Path) -> None:
    """Network/infra flakes before implement should re-queue, not terminally fail."""
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    seeded = _seed_task(settings.db_path)

    with patch("foundry.pipeline.fetch_stage.fetch", return_value=[seeded]), \
         patch(
             "foundry.pipeline.worktree.ensure_base_repo",
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
         patch("foundry.pipeline.worktree.ensure_base_repo", return_value=tmp_path / "base"), \
         patch(
             "foundry.pipeline.worktree.create_worktree",
             return_value=(tmp_path / "wt", "foundry/task-1"),
         ), \
         patch("foundry.pipeline.worktree.cleanup_worktree"), \
         patch("foundry.pipeline.implement_stage.run", side_effect=RuntimeError("boom")):
        processed = pipeline.run_once(settings)

    final = state.get_task(settings.db_path, processed[0].id)
    assert final.status == TaskStatus.FAILED
    assert final.current_stage == Stage.FAILED
    assert final.pr_url is None
