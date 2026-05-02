from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from foundry.config import load_settings
from foundry.models import RunEvent

from .bus import subscribe as bus_subscribe
from .projections import alias_stage

router = APIRouter()


def _parse_last_event_id(raw: str | None) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def format_sse(event: RunEvent) -> bytes:
    """Render an Event as an SSE wire chunk with aliased stage."""
    data = json.dumps(
        {
            "seq": event.seq,
            "stage": alias_stage(event.stage),
            "kind": event.kind,
            "ts_ms": event.ts_ms,
            "payload": event.payload,
        },
        ensure_ascii=False,
    )
    chunk = f"id: {event.seq}\nevent: {event.kind}\ndata: {data}\n\n"
    return chunk.encode("utf-8")


async def sse_stream(
    db_path: Path,
    task_id: int,
    after_seq: int | None,
    *,
    is_disconnected=None,
    poll_interval: float | None = None,
) -> AsyncIterator[bytes]:
    """Core SSE producer — kept separate from the Request for easier testing."""
    async for event in bus_subscribe(
        db_path,
        task_id,
        after_seq=after_seq,
        poll_interval=poll_interval,
        is_disconnected=is_disconnected,
    ):
        yield format_sse(event)


@router.get("/api/tasks/{task_id}/events")
async def stream_events(
    task_id: int,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    after_seq = _parse_last_event_id(last_event_id)
    settings = load_settings()
    return StreamingResponse(
        sse_stream(
            settings.db_path,
            task_id,
            after_seq,
            is_disconnected=request.is_disconnected,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
