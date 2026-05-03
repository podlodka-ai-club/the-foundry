from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from foundry import state


def _table_exists(db: Path, table: str) -> bool:
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def test_init_creates_schema(tmp_path: Path) -> None:
    db = tmp_path / "foundry.sqlite"
    state.init_db(db)
    assert db.exists()
    # running twice must be idempotent
    state.init_db(db)


def test_init_db_creates_required_tables(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    assert _table_exists(db, "events")
    assert _table_exists(db, "runs")
    assert _table_exists(db, "run_events")
    # orchestrator_state was dropped — runs(status='pending') is the queue.
    assert not _table_exists(db, "orchestrator_state")


def test_init_db_drops_legacy_task_events(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE task_events (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()
    assert _table_exists(db, "task_events")

    state.init_db(db)

    assert not _table_exists(db, "task_events")


def test_init_db_drops_legacy_tasks_table(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()
    assert _table_exists(db, "tasks")

    state.init_db(db)

    assert not _table_exists(db, "tasks")


def test_events_unique_constraint(tmp_path: Path) -> None:
    """UNIQUE(trigger_id, external_id) — same dedupe_key reused under
    a different trigger is allowed; reuse under the same trigger is not."""
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO events "
            "(trigger_id, source, external_id, kind, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "github_issues.issue_opened",
                "github_issues",
                "ext-1",
                "issue_opened",
                "{}",
                "2026-01-01T00:00:00Z",
            ),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO events "
                "(trigger_id, source, external_id, kind, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "github_issues.issue_opened",
                    "github_issues",
                    "ext-1",
                    "issue_opened",
                    "{}",
                    "2026-01-01T00:00:00Z",
                ),
            )
            conn.commit()
    finally:
        conn.close()


def test_run_events_unique_run_id_seq(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO run_events (run_id, seq, stage, kind, ts_ms, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, 1, "plan", "stage_started", 0, "{}"),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO run_events (run_id, seq, stage, kind, ts_ms, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (1, 1, "plan", "stage_finished", 1, "{}"),
            )
            conn.commit()
    finally:
        conn.close()
