from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import Stage, Task, TaskStatus, _now_iso

SCHEMA = """
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
            rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY id",
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
