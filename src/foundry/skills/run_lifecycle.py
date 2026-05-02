"""Run-lifecycle skills: mark_done / mark_failed.

Both read run context from environment variables set by the orchestrator
when launching the MCP server subprocess. Compute duration as
"now - run.started_at" and persist the terminal status via state.finish_run,
plus a record_event breadcrumb under the `run_lifecycle` stage.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundry import state
from foundry.events import record_event
from foundry.models import FailureKind, RunStatus

_VALID_FAILURE_KINDS: set[str] = {k.value for k in FailureKind}
_TERMINAL_STATUSES: set[RunStatus] = {
    RunStatus.DONE,
    RunStatus.FAILED,
    RunStatus.UNCLEAR,
}


def _ctx() -> tuple[Path, int, int | None]:
    db_path = Path(os.environ["FOUNDRY_DB_PATH"])
    run_id = int(os.environ["FOUNDRY_RUN_ID"])
    raw_parent = os.environ.get("FOUNDRY_PARENT_EVENT_SEQ")
    parent = int(raw_parent) if raw_parent else None
    return db_path, run_id, parent


def _duration_sec(run_started_at: str) -> float:
    """Best-effort duration; falls back to 0 if parse fails."""
    try:
        started = datetime.fromisoformat(run_started_at)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0.0, (now - started).total_seconds())
    except Exception:
        return 0.0


def mark_done_impl() -> dict[str, Any]:
    """Mark the current run as DONE."""
    db_path, run_id, parent = _ctx()
    run = state.get_run(db_path, run_id)
    if run is not None and run.status in _TERMINAL_STATUSES:
        return {
            "ok": False,
            "error": f"run already terminal: {run.status.value}",
        }
    duration = _duration_sec(run.started_at) if run is not None else 0.0

    state.finish_run(
        db_path,
        run_id,
        status=RunStatus.DONE,
        duration_sec=duration,
    )
    record_event(
        db_path,
        run_id=run_id,
        stage="run_lifecycle",
        kind="mark",
        payload={"action": "done"},
        parent_event_seq=parent,
    )
    return {"ok": True}


def mark_failed_impl(*, kind: str, msg: str) -> dict[str, Any]:
    """Mark the current run as FAILED with a typed failure_kind + msg."""
    if kind not in _VALID_FAILURE_KINDS:
        return {"ok": False, "error": "invalid kind"}

    db_path, run_id, parent = _ctx()
    run = state.get_run(db_path, run_id)
    if run is not None and run.status in _TERMINAL_STATUSES:
        return {
            "ok": False,
            "error": f"run already terminal: {run.status.value}",
        }
    duration = _duration_sec(run.started_at) if run is not None else 0.0

    state.finish_run(
        db_path,
        run_id,
        status=RunStatus.FAILED,
        duration_sec=duration,
        failure_kind=FailureKind(kind),
        failure_msg=msg,
    )
    record_event(
        db_path,
        run_id=run_id,
        stage="run_lifecycle",
        kind="mark",
        payload={"action": "failed", "kind": kind, "msg": msg},
        parent_event_seq=parent,
    )
    return {"ok": True}


# Time helper exposed for tests.
__all__ = ["mark_done_impl", "mark_failed_impl"]
