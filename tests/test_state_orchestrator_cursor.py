from __future__ import annotations

from pathlib import Path

from foundry.state import get_orchestrator_cursor, init_db, set_orchestrator_cursor


def test_get_cursor_default_zero(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)

    assert get_orchestrator_cursor(db) == 0


def test_set_and_get_cursor_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)

    set_orchestrator_cursor(db, 17)

    assert get_orchestrator_cursor(db) == 17

    set_orchestrator_cursor(db, 99)
    assert get_orchestrator_cursor(db) == 99
