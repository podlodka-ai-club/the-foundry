from __future__ import annotations

import os
from pathlib import Path

from foundry import state
from foundry.events import record_event
from foundry.models import RunStatus


def _ctx() -> tuple[Path, int, int | None]:
    db_path = Path(os.environ["FOUNDRY_DB_PATH"])
    run_id = int(os.environ["FOUNDRY_RUN_ID"])
    raw = os.environ.get("FOUNDRY_PARENT_EVENT_SEQ")
    return db_path, run_id, int(raw) if raw else None


def wait_for_human_impl(*, reason: str) -> dict:
    db_path, run_id, parent = _ctx()
    state.update_run(db_path, run_id, status=RunStatus.WAITING, waiting_reason=reason)
    record_event(
        db_path,
        run_id=run_id,
        stage="run_lifecycle",
        kind="mark",
        payload={"action": "waiting", "reason": reason},
        parent_event_seq=parent,
    )
    return {"ok": True}


__all__ = ["wait_for_human_impl"]
