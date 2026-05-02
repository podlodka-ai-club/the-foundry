from __future__ import annotations

from pathlib import Path

from foundry.models import RunStatus
from foundry.state import create_run, get_run, init_db


def test_create_run_returns_int_and_round_trips(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)

    run_id = create_run(
        db,
        automation_id="dev_task",
        event_id=42,
        session_id="abc123",
        session_seq=2,
        status=RunStatus.WAITING,
    )

    assert isinstance(run_id, int)
    assert run_id > 0

    run = get_run(db, run_id)
    assert run is not None
    assert run.id == run_id
    assert run.automation_id == "dev_task"
    assert run.event_id == 42
    assert run.session_id == "abc123"
    assert run.session_seq == 2
    assert run.status is RunStatus.WAITING
    assert run.started_at
    assert run.created_at
    assert run.updated_at
    assert run.finished_at is None
    assert run.failure_kind is None


def test_create_run_defaults(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)

    run_id = create_run(
        db,
        automation_id="dev_task",
        event_id=1,
        session_id="s",
    )

    run = get_run(db, run_id)
    assert run is not None
    assert run.session_seq == 1
    assert run.status is RunStatus.RUNNING


def test_get_run_missing_returns_none(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)

    assert get_run(db, 999) is None
