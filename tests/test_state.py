from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from foundry import state
from foundry.models import Stage, Task, TaskStatus


def _make_task(issue_number: int = 1) -> Task:
    return Task(
        repo="owner/repo",
        issue_number=issue_number,
        issue_title=f"issue {issue_number}",
        issue_body="body",
    )


def test_init_creates_schema(tmp_path: Path) -> None:
    db = tmp_path / "foundry.sqlite"
    state.init_db(db)
    assert db.exists()
    # running twice must be idempotent
    state.init_db(db)


def test_upsert_insert_then_update(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    task = _make_task()
    saved = state.upsert_task(db, task)
    assert saved.id is not None

    saved.status = TaskStatus.RUNNING
    saved.current_stage = Stage.IMPLEMENT
    state.upsert_task(db, saved)

    fetched = state.get_task_by_issue(db, "owner/repo", 1)
    assert fetched is not None
    assert fetched.status == TaskStatus.RUNNING
    assert fetched.current_stage == Stage.IMPLEMENT


def test_list_tasks_filter_by_status(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    t1 = state.upsert_task(db, _make_task(1))
    t2 = state.upsert_task(db, _make_task(2))
    t2.status = TaskStatus.DONE
    state.upsert_task(db, t2)

    pending = state.list_tasks(db, TaskStatus.PENDING)
    done = state.list_tasks(db, TaskStatus.DONE)
    assert [t.issue_number for t in pending] == [1]
    assert [t.issue_number for t in done] == [2]


def test_list_tasks_sorted_desc_by_id(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    t1 = state.upsert_task(db, _make_task(1))
    t2 = state.upsert_task(db, _make_task(2))
    t3 = state.upsert_task(db, _make_task(3))

    tasks = state.list_tasks(db)

    assert [t.id for t in tasks] == [t3.id, t2.id, t1.id]


def test_append_log_accumulates(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    task = state.upsert_task(db, _make_task())

    state.append_log(db, task.id, Stage.PLAN, {"steps": 1})
    state.append_log(db, task.id, Stage.IMPLEMENT, {"ok": True})

    fetched = state.get_task(db, task.id)
    logs = json.loads(fetched.logs_json)
    assert len(logs) == 2
    assert logs[0]["stage"] == "plan"
    assert logs[1]["stage"] == "implement"


def _table_exists(db: Path, table: str) -> bool:
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def test_init_db_creates_events_table(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    assert _table_exists(db, "events")


def test_init_db_creates_runs_table(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    assert _table_exists(db, "runs")


def test_init_db_creates_run_events_table(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    assert _table_exists(db, "run_events")


def test_init_db_drops_legacy_task_events(tmp_path: Path) -> None:
    # Arrange — pre-create the legacy table to simulate an old DB.
    db = tmp_path / "f.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE task_events (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()
    assert _table_exists(db, "task_events")

    # Act
    state.init_db(db)

    # Assert
    assert not _table_exists(db, "task_events")


def test_events_unique_constraint(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO events (source, external_id, kind, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("github_issues", "ext-1", "issue_opened", "{}", "2026-01-01T00:00:00Z"),
        )
        conn.commit()

        # Act / Assert
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO events (source, external_id, kind, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("github_issues", "ext-1", "issue_opened", "{}", "2026-01-01T00:00:00Z"),
            )
            conn.commit()
    finally:
        conn.close()


def test_run_events_unique_run_id_seq(tmp_path: Path) -> None:
    # Arrange
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

        # Act / Assert
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO run_events (run_id, seq, stage, kind, ts_ms, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (1, 1, "plan", "stage_finished", 1, "{}"),
            )
            conn.commit()
    finally:
        conn.close()
