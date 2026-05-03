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

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    stage TEXT NOT NULL,
    kind TEXT NOT NULL,
    ts_ms INTEGER NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE (task_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_task_events_task_seq ON task_events(task_id, seq);

CREATE TABLE IF NOT EXISTS stage_results (
    task_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 0,
    output_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (task_id, stage, attempt)
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    task_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    backend TEXT NOT NULL,
    session_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (task_id, stage, backend)
);

CREATE TABLE IF NOT EXISTS repo_memory (
    repo TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (repo, key)
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


def save_stage_result(
    db_path: Path,
    task_id: int,
    stage: Stage,
    output: dict,
    *,
    attempt: int = 0,
) -> None:
    now = _now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO stage_results (
                task_id, stage, attempt, output_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id, stage, attempt) DO UPDATE SET
                output_json = excluded.output_json,
                updated_at = excluded.updated_at
            """,
            (
                task_id,
                stage.value,
                attempt,
                json.dumps(output),
                now,
                now,
            ),
        )


def get_stage_result(
    db_path: Path,
    task_id: int,
    stage: Stage,
    *,
    attempt: int = 0,
) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT output_json FROM stage_results
            WHERE task_id = ? AND stage = ? AND attempt = ?
            """,
            (task_id, stage.value, attempt),
        ).fetchone()
        return json.loads(row["output_json"]) if row else None


def get_latest_stage_result(
    db_path: Path,
    task_id: int,
    stage: Stage,
) -> tuple[int, dict] | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT attempt, output_json FROM stage_results
            WHERE task_id = ? AND stage = ?
            ORDER BY attempt DESC
            LIMIT 1
            """,
            (task_id, stage.value),
        ).fetchone()
        if row is None:
            return None
        return int(row["attempt"]), json.loads(row["output_json"])


def list_stage_results(
    db_path: Path,
    task_id: int,
    stage: Stage,
) -> list[tuple[int, dict]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT attempt, output_json FROM stage_results
            WHERE task_id = ? AND stage = ?
            ORDER BY attempt ASC
            """,
            (task_id, stage.value),
        ).fetchall()
        return [(int(row["attempt"]), json.loads(row["output_json"])) for row in rows]


def save_repo_memory(db_path: Path, repo: str, key: str, value: object) -> None:
    now = _now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO repo_memory (repo, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(repo, key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (repo, key, json.dumps(value), now),
        )


RepoMemoryValue = dict | list | str | int | float | bool | None


def get_repo_memory(db_path: Path, repo: str, key: str) -> RepoMemoryValue:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT value FROM repo_memory
            WHERE repo = ? AND key = ?
            """,
            (repo, key),
        ).fetchone()
        return json.loads(row["value"]) if row else None


def list_repo_memory(db_path: Path, repo: str) -> list[dict[str, object]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT repo, key, value, updated_at FROM repo_memory
            WHERE repo = ?
            ORDER BY key ASC
            """,
            (repo,),
        ).fetchall()
        return [
            {
                "repo": row["repo"],
                "key": row["key"],
                "value": json.loads(row["value"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]


def save_agent_session(
    db_path: Path,
    task_id: int,
    stage: str,
    backend: str,
    session_id: str,
) -> None:
    now = _now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO agent_sessions (
                task_id, stage, backend, session_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id, stage, backend) DO UPDATE SET
                session_id = excluded.session_id,
                updated_at = excluded.updated_at
            """,
            (task_id, stage, backend, session_id, now, now),
        )


def get_agent_session(
    db_path: Path,
    task_id: int,
    stage: str,
    backend: str,
) -> str | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT session_id FROM agent_sessions
            WHERE task_id = ? AND stage = ? AND backend = ?
            """,
            (task_id, stage, backend),
        ).fetchone()
        return str(row["session_id"]) if row else None
