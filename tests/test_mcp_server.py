from __future__ import annotations

from pathlib import Path

import pytest

from foundry.events import read_events
from foundry.mcp.server import (
    compact_context_impl,
    mark_milestone_impl,
)
from foundry.models import RunStatus
from foundry.state import create_run, init_db


@pytest.fixture
def run_ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, int]:
    db = tmp_path / "f.sqlite"
    init_db(db)
    run_id = create_run(
        db,
        automation_id="dev_task",
        event_id=1,
        session_id="s",
        status=RunStatus.RUNNING,
    )
    monkeypatch.setenv("FOUNDRY_DB_PATH", str(db))
    monkeypatch.setenv("FOUNDRY_RUN_ID", str(run_id))
    monkeypatch.delenv("FOUNDRY_PARENT_EVENT_SEQ", raising=False)
    return db, run_id


def test_mark_milestone_writes_event(run_ctx: tuple[Path, int]) -> None:
    db, run_id = run_ctx

    result = mark_milestone_impl("step 1")

    assert result["ok"] is True
    assert isinstance(result["seq"], int)

    events = read_events(db, run_id=run_id)
    assert len(events) == 1
    ev = events[0]
    assert ev.stage == "milestone"
    assert ev.kind == "mark"
    assert ev.payload == {"label": "step 1"}
    assert ev.parent_event_seq is None


def test_mark_milestone_uses_parent_event_seq_from_env(
    run_ctx: tuple[Path, int], monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, run_id = run_ctx
    monkeypatch.setenv("FOUNDRY_PARENT_EVENT_SEQ", "42")

    mark_milestone_impl("step 2")

    events = read_events(db, run_id=run_id)
    assert len(events) == 1
    assert events[0].parent_event_seq == 42


def test_compact_context_returns_not_implemented() -> None:
    result = compact_context_impl()

    assert result == {"ok": False, "error": "not implemented yet"}
