from __future__ import annotations

from pathlib import Path

import pytest

from foundry.events import read_events
from foundry.models import FailureKind, RunStatus
from foundry.skills.run_lifecycle import mark_done_impl, mark_failed_impl
from foundry.state import create_run, get_run, init_db


@pytest.fixture
def run_ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, int]:
    db = tmp_path / "f.sqlite"
    init_db(db)
    run_id = create_run(
        db,
        automation_id="a",
        event_id=1,
        session_id="s",
        status=RunStatus.RUNNING,
    )
    monkeypatch.setenv("FOUNDRY_DB_PATH", str(db))
    monkeypatch.setenv("FOUNDRY_RUN_ID", str(run_id))
    monkeypatch.delenv("FOUNDRY_PARENT_EVENT_SEQ", raising=False)
    return db, run_id


def test_mark_done_sets_status_and_writes_event(run_ctx: tuple[Path, int]) -> None:
    db, run_id = run_ctx

    out = mark_done_impl()

    assert out == {"ok": True}
    run = get_run(db, run_id)
    assert run is not None
    assert run.status is RunStatus.DONE
    assert run.finished_at is not None

    events = read_events(db, run_id=run_id)
    assert len(events) == 1
    assert events[0].stage == "run_lifecycle"
    assert events[0].kind == "mark"
    assert events[0].payload == {"action": "done"}


def test_mark_failed_with_valid_kind(run_ctx: tuple[Path, int]) -> None:
    db, run_id = run_ctx

    out = mark_failed_impl(kind="infra", msg="boom")

    assert out == {"ok": True}
    run = get_run(db, run_id)
    assert run is not None
    assert run.status is RunStatus.FAILED
    assert run.failure_kind is FailureKind.INFRA
    assert run.failure_msg == "boom"


def test_mark_failed_rejects_invalid_kind(run_ctx: tuple[Path, int]) -> None:
    db, run_id = run_ctx

    out = mark_failed_impl(kind="not-a-kind", msg="x")

    assert out["ok"] is False
    assert "invalid" in out["error"]
    run = get_run(db, run_id)
    assert run is not None
    # Run remains running, untouched.
    assert run.status is RunStatus.RUNNING


def test_mark_done_rejected_when_run_already_terminal(
    run_ctx: tuple[Path, int],
) -> None:
    """Regression: mark_done must not resurrect a finalized run (e.g. one
    already stopped by the user via POST /stop)."""
    db, run_id = run_ctx
    # First call wins.
    assert mark_done_impl() == {"ok": True}

    # Second call must be rejected — without this guard, an agent could
    # overwrite a user-initiated `stop` or another mark.
    out = mark_done_impl()
    assert out["ok"] is False
    assert "terminal" in out["error"]


def test_mark_failed_rejected_when_run_already_terminal(
    run_ctx: tuple[Path, int],
) -> None:
    db, run_id = run_ctx
    assert mark_done_impl() == {"ok": True}

    out = mark_failed_impl(kind="infra", msg="late")
    assert out["ok"] is False
    assert "terminal" in out["error"]
    run = get_run(db, run_id)
    assert run is not None
    # First terminal status wins; failure_kind/msg stay None.
    assert run.status is RunStatus.DONE
    assert run.failure_kind is None
