from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .models import Event, FailureKind, Run, RunStatus, _now_iso

SCHEMA = """
DROP TABLE IF EXISTS task_events;
DROP TABLE IF EXISTS tasks;

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
    agent_session_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orchestrator_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_seen_event_id INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO orchestrator_state (id, last_seen_event_id, updated_at)
VALUES (1, 0, '');

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


def _row_to_run(row: sqlite3.Row) -> Run:
    failure_kind_raw = row["failure_kind"]
    keys = row.keys()
    agent_session_id = row["agent_session_id"] if "agent_session_id" in keys else None
    return Run(
        id=row["id"],
        automation_id=row["automation_id"],
        event_id=row["event_id"],
        session_id=row["session_id"],
        session_seq=row["session_seq"],
        status=RunStatus(row["status"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        duration_sec=row["duration_sec"],
        cost_usd=row["cost_usd"],
        failure_kind=FailureKind(failure_kind_raw) if failure_kind_raw else None,
        failure_msg=row["failure_msg"],
        waiting_reason=row["waiting_reason"],
        agent_session_id=agent_session_id,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_run(
    db_path: Path,
    *,
    automation_id: str,
    event_id: int,
    session_id: str,
    session_seq: int = 1,
    status: RunStatus = RunStatus.RUNNING,
) -> int:
    """Insert a new run, return its id."""
    now = _now_iso()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO runs (
                automation_id, event_id, session_id, session_seq,
                status, started_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                automation_id,
                event_id,
                session_id,
                session_seq,
                status.value,
                now,
                now,
                now,
            ),
        )
        return int(cur.lastrowid)


def get_run(db_path: Path, run_id: int) -> Run | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row else None


def update_run(
    db_path: Path,
    run_id: int,
    *,
    status: RunStatus | None = None,
    failure_kind: FailureKind | None = None,
    failure_msg: str | None = None,
    waiting_reason: str | None = None,
    finished_at: str | None = None,
    duration_sec: float | None = None,
    cost_usd: float | None = None,
    agent_session_id: str | None = None,
) -> None:
    """Partial update — None means leave as-is. Always bumps updated_at."""
    sets: list[str] = []
    params: list[Any] = []
    if status is not None:
        sets.append("status = ?")
        params.append(status.value)
    if failure_kind is not None:
        sets.append("failure_kind = ?")
        params.append(failure_kind.value)
    if failure_msg is not None:
        sets.append("failure_msg = ?")
        params.append(failure_msg)
    if waiting_reason is not None:
        sets.append("waiting_reason = ?")
        params.append(waiting_reason)
    if finished_at is not None:
        sets.append("finished_at = ?")
        params.append(finished_at)
    if duration_sec is not None:
        sets.append("duration_sec = ?")
        params.append(duration_sec)
    if cost_usd is not None:
        sets.append("cost_usd = ?")
        params.append(cost_usd)
    if agent_session_id is not None:
        sets.append("agent_session_id = ?")
        params.append(agent_session_id)

    sets.append("updated_at = ?")
    params.append(_now_iso())
    params.append(run_id)

    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE runs SET {', '.join(sets)} WHERE id = ?",
            tuple(params),
        )


def finish_run(
    db_path: Path,
    run_id: int,
    *,
    status: RunStatus,
    duration_sec: float,
    cost_usd: float | None = None,
    failure_kind: FailureKind | None = None,
    failure_msg: str | None = None,
) -> None:
    """Set finished_at=now and apply terminal fields via update_run."""
    update_run(
        db_path,
        run_id,
        status=status,
        duration_sec=duration_sec,
        cost_usd=cost_usd,
        failure_kind=failure_kind,
        failure_msg=failure_msg,
        finished_at=_now_iso(),
    )


def next_session_seq(db_path: Path, session_id: str) -> int:
    """Return MAX(session_seq)+1 for the given session_id, or 1 if no rows."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(session_seq), 0) + 1 FROM runs WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row[0])


def list_runs(
    db_path: Path,
    *,
    automation_id: str | None = None,
    status: RunStatus | None = None,
    limit: int = 100,
) -> list[Run]:
    sql = "SELECT * FROM runs"
    where: list[str] = []
    params: list[Any] = []
    if automation_id is not None:
        where.append("automation_id = ?")
        params.append(automation_id)
    if status is not None:
        where.append("status = ?")
        params.append(status.value)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _connect(db_path) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [_row_to_run(r) for r in rows]


def find_running_run(
    db_path: Path,
    *,
    event_id: int,
    automation_id: str,
) -> Run | None:
    """Return the running run for (event_id, automation_id), or None."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE event_id = ? AND automation_id = ? AND status = ? "
            "ORDER BY id DESC LIMIT 1",
            (event_id, automation_id, RunStatus.RUNNING.value),
        ).fetchone()
        return _row_to_run(row) if row else None


def count_runs_by_automation_status(
    db_path: Path,
) -> dict[tuple[str, str], int]:
    """Returns {(automation_id, status): count} aggregated over all runs."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT automation_id, status, COUNT(*) AS n "
            "FROM runs GROUP BY automation_id, status"
        ).fetchall()
        return {(row["automation_id"], row["status"]): int(row["n"]) for row in rows}


def last_event_at_by_source(db_path: Path) -> dict[str, str]:
    """Returns {source: max(created_at)} across the events table."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT source, MAX(created_at) AS last_seen FROM events GROUP BY source"
        ).fetchall()
        return {row["source"]: row["last_seen"] for row in rows if row["last_seen"]}


def get_orchestrator_cursor(db_path: Path) -> int:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT last_seen_event_id FROM orchestrator_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return 0
        return int(row[0])


def set_orchestrator_cursor(db_path: Path, last_seen_event_id: int) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE orchestrator_state SET last_seen_event_id = ?, updated_at = ? WHERE id = 1",
            (last_seen_event_id, _now_iso()),
        )
