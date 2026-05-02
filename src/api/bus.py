from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import AsyncIterator

from foundry.events import read_events
from foundry.models import RunEvent


def _default_poll_interval() -> float:
    raw = os.environ.get("FOUNDRY_SSE_POLL_SEC", "").strip()
    if not raw:
        return 0.5
    try:
        return float(raw)
    except ValueError:
        return 0.5


POLL_SEC = _default_poll_interval()


async def subscribe(
    db_path: Path,
    run_id: int,
    after_seq: int | None = None,
    *,
    poll_interval: float | None = None,
    is_disconnected=None,
) -> AsyncIterator[RunEvent]:
    """Yield events for `run_id` in seq order by polling SQLite.

    Works across processes — the orchestrator writer and the API reader do
    not need to share memory. Catch-up and live phases are unified: every
    tick is a single `read_events(..., after_seq=last_seen)` call. SQLite
    reads are offloaded to a worker thread so uvicorn's event loop stays
    responsive.
    """
    interval = POLL_SEC if poll_interval is None else poll_interval
    last_seen = after_seq or 0

    while True:
        events = await asyncio.to_thread(
            read_events, db_path, run_id, after_seq=last_seen
        )
        for ev in events:
            last_seen = ev.seq
            yield ev

        if is_disconnected is not None and await is_disconnected():
            break

        await asyncio.sleep(interval)
