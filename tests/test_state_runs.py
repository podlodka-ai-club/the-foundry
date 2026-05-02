from __future__ import annotations

from pathlib import Path

from foundry.models import FailureKind, RunStatus
from foundry.state import (
    create_run,
    find_running_run,
    finish_run,
    get_run,
    init_db,
    list_runs,
    next_session_seq,
    update_run,
)


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


def test_update_run_partial_only_sets_provided(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    run_id = create_run(db, automation_id="a", event_id=1, session_id="s")

    update_run(db, run_id, status=RunStatus.WAITING, waiting_reason="for human")

    run = get_run(db, run_id)
    assert run is not None
    assert run.status is RunStatus.WAITING
    assert run.waiting_reason == "for human"
    # Untouched fields stay unset
    assert run.failure_kind is None
    assert run.failure_msg is None
    assert run.finished_at is None
    assert run.duration_sec is None


def test_update_run_failure_kind_round_trips(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    run_id = create_run(db, automation_id="a", event_id=1, session_id="s")

    update_run(
        db,
        run_id,
        status=RunStatus.FAILED,
        failure_kind=FailureKind.INFRA,
        failure_msg="boom",
    )

    run = get_run(db, run_id)
    assert run is not None
    assert run.status is RunStatus.FAILED
    assert run.failure_kind is FailureKind.INFRA
    assert run.failure_msg == "boom"


def test_finish_run_sets_finished_at_and_duration(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    run_id = create_run(db, automation_id="a", event_id=1, session_id="s")

    finish_run(db, run_id, status=RunStatus.DONE, duration_sec=12.5, cost_usd=0.01)

    run = get_run(db, run_id)
    assert run is not None
    assert run.status is RunStatus.DONE
    assert run.duration_sec == 12.5
    assert run.cost_usd == 0.01
    assert run.finished_at is not None


def test_next_session_seq_starts_at_1(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)

    assert next_session_seq(db, "fresh-session") == 1


def test_next_session_seq_increments_per_session(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    create_run(db, automation_id="a", event_id=1, session_id="s1", session_seq=1)
    create_run(db, automation_id="a", event_id=2, session_id="s1", session_seq=2)
    create_run(db, automation_id="a", event_id=3, session_id="other", session_seq=1)

    assert next_session_seq(db, "s1") == 3
    assert next_session_seq(db, "other") == 2


def test_list_runs_filter_by_status(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    r1 = create_run(db, automation_id="a", event_id=1, session_id="s")
    r2 = create_run(db, automation_id="a", event_id=2, session_id="s2")
    update_run(db, r2, status=RunStatus.DONE)

    running = list_runs(db, status=RunStatus.RUNNING)
    done = list_runs(db, status=RunStatus.DONE)

    assert {r.id for r in running} == {r1}
    assert {r.id for r in done} == {r2}


def test_list_runs_filter_by_automation(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    r1 = create_run(db, automation_id="a", event_id=1, session_id="s")
    create_run(db, automation_id="b", event_id=2, session_id="s2")

    rs = list_runs(db, automation_id="a")

    assert {r.id for r in rs} == {r1}


def test_find_running_run_returns_running_only(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    r1 = create_run(db, automation_id="a", event_id=42, session_id="s")

    found = find_running_run(db, event_id=42, automation_id="a")
    assert found is not None
    assert found.id == r1

    update_run(db, r1, status=RunStatus.DONE)
    assert find_running_run(db, event_id=42, automation_id="a") is None


def test_find_running_run_no_match_returns_none(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)

    assert find_running_run(db, event_id=99, automation_id="a") is None


def test_run_status_pending_round_trips(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)

    run_id = create_run(
        db,
        automation_id="a",
        event_id=1,
        session_id="s",
        status=RunStatus.PENDING,
    )

    run = get_run(db, run_id)
    assert run is not None
    assert run.status is RunStatus.PENDING

    rs = list_runs(db, status=RunStatus.PENDING)
    assert {r.id for r in rs} == {run_id}


def test_run_status_unclear_round_trips(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    run_id = create_run(db, automation_id="a", event_id=1, session_id="s")

    update_run(db, run_id, status=RunStatus.UNCLEAR)

    run = get_run(db, run_id)
    assert run is not None
    assert run.status is RunStatus.UNCLEAR


def test_update_run_persists_agent_session_id(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    run_id = create_run(db, automation_id="a", event_id=1, session_id="s")

    update_run(db, run_id, agent_session_id="claude-sess-xyz")

    run = get_run(db, run_id)
    assert run is not None
    assert run.agent_session_id == "claude-sess-xyz"
