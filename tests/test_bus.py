from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from api.bus import subscribe
from foundry import state
from foundry.events import record_event
from foundry.models import RunEvent


@pytest.mark.asyncio
async def test_bus_subscribe_yields_catchup_events(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    for i in range(3):
        record_event(db, 1, "plan", "agent_text", {"text": f"msg-{i}"})

    # Act
    received: list[RunEvent] = []
    agen = subscribe(db, run_id=1, poll_interval=0.05)
    try:
        for _ in range(3):
            received.append(await asyncio.wait_for(agen.__anext__(), timeout=1.0))
    finally:
        await agen.aclose()

    # Assert
    assert [ev.seq for ev in received] == [1, 2, 3]
    assert received[0].payload == {"text": "msg-0"}


@pytest.mark.asyncio
async def test_bus_subscribe_yields_live_events_after_catchup(tmp_path: Path) -> None:
    # Arrange — empty DB, subscriber starts before any events exist.
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    agen = subscribe(db, run_id=1, poll_interval=0.05)

    # Act: schedule a write after the generator enters its poll loop.
    async def _publish_later() -> None:
        await asyncio.sleep(0.1)
        record_event(db, 1, "plan", "agent_text", {"text": "live"})

    publisher = asyncio.create_task(_publish_later())
    try:
        event = await asyncio.wait_for(agen.__anext__(), timeout=3.0)
    finally:
        await publisher
        await agen.aclose()

    # Assert
    assert event.seq == 1
    assert event.payload == {"text": "live"}


@pytest.mark.asyncio
async def test_bus_subscribe_filters_by_after_seq(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    for i in range(5):
        record_event(db, 1, "plan", "agent_text", {"text": f"m{i}"})

    # Act
    received: list[RunEvent] = []
    agen = subscribe(db, run_id=1, after_seq=3, poll_interval=0.05)
    try:
        for _ in range(2):
            received.append(await asyncio.wait_for(agen.__anext__(), timeout=1.0))
    finally:
        await agen.aclose()

    # Assert
    assert [ev.seq for ev in received] == [4, 5]


@pytest.mark.asyncio
async def test_bus_subscribe_closes_when_run_terminal(tmp_path: Path) -> None:
    """Regression: SSE generator must self-terminate after the run reaches a
    terminal status — otherwise abandoned EventSource connections poll
    forever."""
    from foundry.models import RunStatus

    db = tmp_path / "f.sqlite"
    state.init_db(db)
    run_id = state.create_run(
        db, automation_id="a", event_id=1, session_id="s", status=RunStatus.DONE,
    )
    record_event(db, run_id, "run_lifecycle", "mark", {"action": "done"})

    agen = subscribe(db, run_id=run_id, poll_interval=0.02)
    received: list[RunEvent] = []
    # Drain — generator should yield existing event then exit on next iteration.
    async for ev in agen:
        received.append(ev)
        if len(received) > 5:  # safety net against infinite loop regression
            break

    assert len(received) == 1
    assert received[0].kind == "mark"
