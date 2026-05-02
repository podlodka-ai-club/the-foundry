from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from api.sse import _parse_last_event_id, format_sse, sse_stream
from foundry import state
from foundry.events import record_event
from foundry.models import RunEvent, Task


@pytest.fixture
def _db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.sqlite"
    state.init_db(db_path)
    return db_path


def _make_task(db: Path, issue_number: int = 1) -> Task:
    return state.upsert_task(
        db,
        Task(
            repo="owner/repo",
            issue_number=issue_number,
            issue_title="t",
            issue_body="",
        ),
    )


def _collect_ids(chunks: list[bytes]) -> list[int]:
    ids: list[int] = []
    for c in chunks:
        for line in c.decode("utf-8").splitlines():
            if line.startswith("id: "):
                ids.append(int(line.removeprefix("id: ").strip()))
    return ids


def test_parse_last_event_id_variants() -> None:
    assert _parse_last_event_id(None) is None
    assert _parse_last_event_id("") is None
    assert _parse_last_event_id("3") == 3
    assert _parse_last_event_id("bad") is None


def test_format_sse_shape() -> None:
    # Arrange
    ev = RunEvent(
        id=1,
        run_id=1,
        seq=5,
        stage="plan",
        kind="agent_text",
        ts_ms=12345,
        payload={"text": "hi"},
    )

    # Act
    chunk = format_sse(ev).decode("utf-8")

    # Assert — id is raw seq, event is kind, data is JSON with aliased stage.
    assert chunk.startswith("id: 5\n")
    assert "event: agent_text\n" in chunk
    assert chunk.endswith("\n\n")
    data_line = [l for l in chunk.splitlines() if l.startswith("data: ")][0]
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload["stage"] == "agent_plan"
    assert payload["seq"] == 5


async def test_sse_replays_from_last_event_id(_db: Path) -> None:
    # Arrange
    task = _make_task(_db)
    for i in range(5):
        record_event(_db, task.id, "plan", "agent_text", {"text": f"m{i}"})

    # Act: no Last-Event-ID → all 5.
    agen = sse_stream(_db, task.id, after_seq=None, poll_interval=0.05)
    all_chunks: list[bytes] = []
    for _ in range(5):
        all_chunks.append(await asyncio.wait_for(agen.__anext__(), timeout=1.0))
    await agen.aclose()

    # Act 2: Last-Event-ID=3 → only 4, 5.
    agen2 = sse_stream(_db, task.id, after_seq=3, poll_interval=0.05)
    tail_chunks: list[bytes] = []
    for _ in range(2):
        tail_chunks.append(await asyncio.wait_for(agen2.__anext__(), timeout=1.0))
    await agen2.aclose()

    # Assert
    assert _collect_ids(all_chunks) == [1, 2, 3, 4, 5]
    assert _collect_ids(tail_chunks) == [4, 5]


async def test_sse_live_event_pushes(_db: Path) -> None:
    # Arrange
    task = _make_task(_db, issue_number=2)
    agen = sse_stream(_db, task.id, after_seq=None, poll_interval=0.05)

    # Act: schedule a live record_event while the generator is awaiting queue.
    async def _publish_later() -> None:
        await asyncio.sleep(0.1)
        record_event(_db, task.id, "plan", "agent_text", {"text": "hello-live"})

    publisher = asyncio.create_task(_publish_later())
    chunk = await asyncio.wait_for(agen.__anext__(), timeout=3.0)
    await publisher
    await agen.aclose()

    # Assert
    assert _collect_ids([chunk]) == [1]
    assert b"hello-live" in chunk
