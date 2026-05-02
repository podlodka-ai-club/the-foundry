from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from api import bus
from foundry import state
from foundry.events import record_event
from foundry.models import RunEvent


@pytest.mark.asyncio
async def test_sse_streams_via_bus_subscribe(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    eid = state.record_external_event(
        db,
        source="github_issues",
        external_id="repo#1",
        kind="issue.opened",
        payload={"title": "x"},
    )
    assert eid is not None
    rid = state.create_run(db, automation_id="dev_task", event_id=eid, session_id="s")
    record_event(db, rid, "plan", "agent_text", {"text": "hello"})

    # Act
    received: list[RunEvent] = []
    agen = bus.subscribe(db, run_id=rid, poll_interval=0.05)
    try:
        received.append(await asyncio.wait_for(agen.__anext__(), timeout=1.0))
    finally:
        await agen.aclose()

    # Assert
    assert len(received) == 1
    assert received[0].seq == 1
    assert received[0].payload == {"text": "hello"}
