from __future__ import annotations

from pathlib import Path

import pytest

from foundry.events import read_events
from foundry.models import RunStatus
from foundry.skills.wait_for_human import wait_for_human_impl
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


def test_wait_for_human_sets_run_to_waiting(run_ctx: tuple[Path, int]) -> None:
    db, run_id = run_ctx

    out = wait_for_human_impl(reason="need approval")

    assert out == {"ok": True}
    run = get_run(db, run_id)
    assert run is not None
    assert run.status is RunStatus.WAITING
    assert run.waiting_reason == "need approval"


def test_wait_for_human_writes_mark_event(run_ctx: tuple[Path, int]) -> None:
    db, run_id = run_ctx

    wait_for_human_impl(reason="please review")

    events = read_events(db, run_id=run_id)
    assert len(events) == 1
    ev = events[0]
    assert ev.stage == "run_lifecycle"
    assert ev.kind == "mark"
    assert ev.payload == {"action": "waiting", "reason": "please review"}
