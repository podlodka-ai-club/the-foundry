from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .models import Event, Stage, Task, TaskStatus, _now_iso

SCHEMA = """
DROP TABLE IF EXISTS task_events;

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    issue_title TEXT NOT NULL,
    issue_body TEXT NOT NULL,
    status TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    worktree_path TEXT,
    branch_name TEXT,
    pr_url TEXT,
    logs_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (repo, issue_number)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    parent_event_id INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    automation_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    session_seq INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_sec REAL,
    cost_usd REAL,
    failure_kind TEXT,
    failure_msg TEXT,
    waiting_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    parent_event_seq INTEGER,
    stage TEXT NOT NULL,
    kind TEXT NOT NULL,
    ts_ms INTEGER NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE (run_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_events_source_created ON events(source, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_automation ON runs(automation_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id, session_seq);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_event ON runs(event_id);
CREATE INDEX IF NOT EXISTS idx_run_events_run_seq ON run_events(run_id, seq);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        repo=row["repo"],
        issue_number=row["issue_number"],
        issue_title=row["issue_title"],
        issue_body=row["issue_body"],
        status=TaskStatus(row["status"]),
        current_stage=Stage(row["current_stage"]),
        attempts=row["attempts"],
        worktree_path=row["worktree_path"],
        branch_name=row["branch_name"],
        pr_url=row["pr_url"],
        logs_json=row["logs_json"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_task_by_issue(db_path: Path, repo: str, issue_number: int) -> Task | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE repo = ? AND issue_number = ?",
            (repo, issue_number),
        ).fetchone()
        return _row_to_task(row) if row else None


def get_task(db_path: Path, task_id: int) -> Task | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None


def list_tasks(db_path: Path, status: TaskStatus | None = None) -> list[Task]:
    with _connect(db_path) as conn:
        if status is None:
            rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY id DESC",
                (status.value,),
            ).fetchall()
        return [_row_to_task(r) for r in rows]


def upsert_task(db_path: Path, task: Task) -> Task:
    task.updated_at = _now_iso()
    with _connect(db_path) as conn:
        if task.id is None:
            cur = conn.execute(
                """
                INSERT INTO tasks (
                    repo, issue_number, issue_title, issue_body,
                    status, current_stage, attempts,
                    worktree_path, branch_name, pr_url, logs_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.repo,
                    task.issue_number,
                    task.issue_title,
                    task.issue_body,
                    task.status.value,
                    task.current_stage.value,
                    task.attempts,
                    task.worktree_path,
                    task.branch_name,
                    task.pr_url,
                    task.logs_json,
                    task.created_at,
                    task.updated_at,
                ),
            )
            task.id = cur.lastrowid
        else:
            conn.execute(
                """
                UPDATE tasks SET
                    issue_title = ?, issue_body = ?,
                    status = ?, current_stage = ?, attempts = ?,
                    worktree_path = ?, branch_name = ?, pr_url = ?, logs_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    task.issue_title,
                    task.issue_body,
                    task.status.value,
                    task.current_stage.value,
                    task.attempts,
                    task.worktree_path,
                    task.branch_name,
                    task.pr_url,
                    task.logs_json,
                    task.updated_at,
                    task.id,
                ),
            )
        return task


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        source=row["source"],
        external_id=row["external_id"],
        kind=row["kind"],
        payload=json.loads(row["payload"]),
        parent_event_id=row["parent_event_id"],
        created_at=row["created_at"],
    )


def record_external_event(
    db_path: Path,
    *,
    source: str,
    external_id: str,
    kind: str,
    payload: dict[str, Any],
    parent_event_id: int | None = None,
) -> int | None:
    """Insert a top-level trigger event with dedupe on (source, external_id).

    Uses INSERT … ON CONFLICT(source, external_id) DO NOTHING. Returns the
    inserted row id on success, or None when a row with the same
    (source, external_id) already exists (duplicate).
    """
    payload_json = json.dumps(payload, ensure_ascii=False)
    created_at = _now_iso()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO events (source, external_id, kind, payload, parent_event_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, external_id) DO NOTHING
            """,
            (source, external_id, kind, payload_json, parent_event_id, created_at),
        )
        if cur.rowcount == 1:
            return cur.lastrowid
        return None


def read_events_after(
    db_path: Path,
    *,
    after_id: int = 0,
    limit: int = 100,
) -> list[Event]:
    """Return events with id > after_id in ASC order, capped by limit."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE id > ? ORDER BY id ASC LIMIT ?",
            (after_id, limit),
        ).fetchall()
        return [_row_to_event(r) for r in rows]


def get_event(db_path: Path, event_id: int) -> Event | None:
    """Single-row read by id, returns None if missing."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        return _row_to_event(row) if row else None


def append_log(db_path: Path, task_id: int, stage: Stage, entry: dict) -> None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT logs_json FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return
        logs = json.loads(row["logs_json"] or "[]")
        logs.append({"stage": stage.value, "at": _now_iso(), **entry})
        conn.execute(
            "UPDATE tasks SET logs_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(logs), _now_iso(), task_id),
        )
