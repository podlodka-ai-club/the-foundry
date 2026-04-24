from __future__ import annotations

import json
import sqlite3
import time
import traceback as _traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from .models import Event

_TRUNCATE_FIELDS = {"text", "stdout", "stderr", "input", "output"}
_MAX_FIELD_BYTES = 64 * 1024


def _truncate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Recursively walk payload; replace long string fields in _TRUNCATE_FIELDS
    whose utf-8 size exceeds 64KB with a truncation marker. Other fields are
    untouched. Returns a new dict (original is not mutated)."""
    return _walk(payload)


def _walk(value: Any, *, field_name: str | None = None) -> Any:
    if isinstance(value, dict):
        return {k: _walk(v, field_name=k) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(item, field_name=field_name) for item in value]
    if isinstance(value, str) and field_name in _TRUNCATE_FIELDS:
        return _maybe_truncate_string(value)
    return value


def _maybe_truncate_string(s: str) -> Any:
    encoded = s.encode("utf-8")
    if len(encoded) <= _MAX_FIELD_BYTES:
        return s
    # Take first 64KB of utf-8 and decode safely (drop trailing partial char).
    head_bytes = encoded[:_MAX_FIELD_BYTES]
    head = head_bytes.decode("utf-8", errors="ignore")
    return {
        "text": head,
        "truncated": True,
        "original_size": len(encoded),
    }


def record_event(
    db_path: Path,
    task_id: int,
    stage: str,
    kind: str,
    payload: dict[str, Any],
) -> int:
    """Append an event for task_id. Returns the assigned per-task seq.

    Atomic under concurrent writers: MAX(seq)+1 and INSERT happen inside a
    single transaction guarded by SQLite's UNIQUE(task_id, seq) constraint.
    """
    truncated = _truncate_payload(payload)
    payload_json = json.dumps(truncated, ensure_ascii=False)
    ts_ms = int(time.time() * 1000)

    # Per-call connection so multiple threads don't fight over a shared handle.
    conn = sqlite3.connect(db_path, isolation_level="IMMEDIATE", timeout=30.0)
    try:
        while True:
            try:
                cur = conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) + 1 FROM task_events WHERE task_id = ?",
                    (task_id,),
                )
                seq = cur.fetchone()[0]
                conn.execute(
                    "INSERT INTO task_events (task_id, seq, stage, kind, ts_ms, payload) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (task_id, seq, stage, kind, ts_ms, payload_json),
                )
                conn.commit()
                return seq
            except sqlite3.IntegrityError:
                # Seq assignment relies on UNIQUE(task_id, seq) + retry, not locking.
                # The SELECT above runs unprotected (BEGIN fires only before INSERT),
                # so a concurrent writer may grab the same seq first — roll back and
                # retry; MAX(seq) will have advanced.
                conn.rollback()
                continue
    finally:
        conn.close()


def read_events(
    db_path: Path,
    task_id: int,
    after_seq: int | None = None,
    limit: int | None = None,
) -> list[Event]:
    """Read events for task_id in seq ASC order. If after_seq is set, only
    events with seq > after_seq are returned."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT id, task_id, seq, stage, kind, ts_ms, payload FROM task_events WHERE task_id = ?"
        params: list[Any] = [task_id]
        if after_seq is not None:
            sql += " AND seq > ?"
            params.append(after_seq)
        sql += " ORDER BY seq ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [
            Event(
                id=row["id"],
                task_id=row["task_id"],
                seq=row["seq"],
                stage=row["stage"],
                kind=row["kind"],
                ts_ms=row["ts_ms"],
                payload=json.loads(row["payload"]),
            )
            for row in rows
        ]
    finally:
        conn.close()


@contextmanager
def stage_span(
    db_path: Path,
    task_id: int,
    stage: str,
    *,
    input: dict[str, Any] | None = None,
    agent: dict[str, Any] | None = None,
) -> Iterator[Callable[..., None]]:
    """Emit stage_started on entry and stage_finished / stage_failed on exit.

    Yields a `finish(output=None, cost_usd=None, tokens_in=None, tokens_out=None)`
    callback. Calling it is optional — if omitted, stage_finished is still
    emitted on a clean exit with `output=None`. On exception, stage_failed
    (with repr(exc) and traceback) is emitted instead, and the exception is
    re-raised; stage_finished is NOT emitted.
    """
    started_payload: dict[str, Any] = {}
    if input is not None:
        started_payload["input"] = input
    if agent is not None:
        started_payload["agent"] = agent
    record_event(db_path, task_id, stage, "stage_started", started_payload)

    t0 = time.monotonic()
    meta: dict[str, Any] = {}

    def finish(
        output: Any = None,
        cost_usd: float | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
    ) -> None:
        meta["output"] = output
        meta["cost_usd"] = cost_usd
        meta["tokens_in"] = tokens_in
        meta["tokens_out"] = tokens_out
        meta["_called"] = True

    try:
        yield finish
    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        record_event(
            db_path,
            task_id,
            stage,
            "stage_failed",
            {
                "duration_ms": duration_ms,
                "error": repr(exc),
                "traceback": _traceback.format_exc(),
            },
        )
        raise

    duration_ms = int((time.monotonic() - t0) * 1000)
    finished_payload: dict[str, Any] = {"duration_ms": duration_ms}
    if meta.get("_called"):
        # Only include optional fields that were actually set to non-None.
        if meta.get("output") is not None:
            finished_payload["output"] = meta["output"]
        if meta.get("cost_usd") is not None:
            finished_payload["cost_usd"] = meta["cost_usd"]
        if meta.get("tokens_in") is not None:
            finished_payload["tokens_in"] = meta["tokens_in"]
        if meta.get("tokens_out") is not None:
            finished_payload["tokens_out"] = meta["tokens_out"]
    record_event(db_path, task_id, stage, "stage_finished", finished_payload)
