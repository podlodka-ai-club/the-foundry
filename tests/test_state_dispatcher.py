"""Tests for the new dispatcher-side primitives: ``claim_pending_run`` and
``recover_orphan_runs``. These replace the old cursor/pickup pair that was
deleted along with ``orchestrator_state``."""

from __future__ import annotations

from pathlib import Path

from foundry.models import FailureKind, RunStatus
from foundry.state import (
    claim_pending_run,
    create_run,
    get_run,
    init_db,
    recover_orphan_runs,
)


def test_claim_returns_none_on_empty_queue(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)

    assert claim_pending_run(db) is None


def test_claim_flips_pending_to_running_atomically(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    rid = create_run(
        db,
        automation_id="a",
        event_id=1,
        session_id="s",
        status=RunStatus.PENDING,
    )

    claimed = claim_pending_run(db)

    assert claimed is not None
    assert claimed.id == rid
    assert claimed.status is RunStatus.RUNNING
    # Persisted to DB.
    refreshed = get_run(db, rid)
    assert refreshed is not None and refreshed.status is RunStatus.RUNNING


def test_claim_picks_oldest_pending(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    older = create_run(
        db, automation_id="a", event_id=1, session_id="s1",
        status=RunStatus.PENDING,
    )
    create_run(
        db, automation_id="a", event_id=2, session_id="s2",
        status=RunStatus.PENDING,
    )

    claimed = claim_pending_run(db)
    assert claimed is not None
    assert claimed.id == older


def test_claim_skips_already_running(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    create_run(
        db, automation_id="a", event_id=1, session_id="s",
        status=RunStatus.RUNNING,
    )

    assert claim_pending_run(db) is None


def test_recover_orphan_runs_marks_running_as_failed_infra(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    orphaned = create_run(
        db, automation_id="a", event_id=1, session_id="s",
        status=RunStatus.RUNNING,
    )
    pending = create_run(
        db, automation_id="b", event_id=2, session_id="t",
        status=RunStatus.PENDING,
    )

    count = recover_orphan_runs(db)

    assert count == 1
    o = get_run(db, orphaned)
    assert o is not None
    assert o.status is RunStatus.FAILED
    assert o.failure_kind is FailureKind.INFRA
    assert o.failure_msg == "orphaned on restart"
    # PENDING is left alone.
    p = get_run(db, pending)
    assert p is not None and p.status is RunStatus.PENDING


def test_recover_orphan_runs_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)

    assert recover_orphan_runs(db) == 0
    assert recover_orphan_runs(db) == 0
