from __future__ import annotations

from pathlib import Path

import pytest

from foundry.events import read_events
from foundry.mcp.runner import run_subagent
from foundry.models import RunStatus
from foundry.state import create_run, init_db


@pytest.fixture
def run_ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, int]:
    db = tmp_path / "f.sqlite"
    init_db(db)
    run_id = create_run(
        db,
        automation_id="dev_task",
        event_id=1,
        session_id="parent-session",
        status=RunStatus.RUNNING,
    )
    monkeypatch.setenv("FOUNDRY_DB_PATH", str(db))
    monkeypatch.setenv("FOUNDRY_RUN_ID", str(run_id))
    monkeypatch.setenv("FOUNDRY_WORKTREE", str(tmp_path))
    monkeypatch.delenv("FOUNDRY_PARENT_EVENT_SEQ", raising=False)
    return db, run_id


def test_run_subagent_unknown_returns_error(run_ctx: tuple[Path, int]) -> None:
    db, run_id = run_ctx

    result = run_subagent(name="nope", prompt="hi", caller_id="caller-1")

    assert result["ok"] is False
    assert "nope" in result["error"]
    # No events written for unknown sub-agent.
    assert read_events(db, run_id=run_id) == []


def test_run_subagent_echo_writes_call_started_and_finished(
    run_ctx: tuple[Path, int],
) -> None:
    db, run_id = run_ctx

    result = run_subagent(name="echo", prompt="hello world", caller_id="caller-1")

    assert result["ok"] is True
    assert result["sub_session_id"]

    events = read_events(db, run_id=run_id)
    kinds = [e.kind for e in events]
    assert "agent_call_started" in kinds
    assert "agent_call_finished" in kinds
    framing = [e for e in events if e.kind in ("agent_call_started", "agent_call_finished")]
    for ev in framing:
        assert ev.stage == "subagent:echo"
        assert ev.parent_event_seq is None  # no FOUNDRY_PARENT_EVENT_SEQ set


def test_run_subagent_propagates_parent_event_seq_to_inner_events(
    run_ctx: tuple[Path, int], monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, run_id = run_ctx
    monkeypatch.setenv("FOUNDRY_PARENT_EVENT_SEQ", "10")

    run_subagent(name="echo", prompt="hi", caller_id="caller-2")

    events = read_events(db, run_id=run_id)
    started = next(e for e in events if e.kind == "agent_call_started")
    finished = next(e for e in events if e.kind == "agent_call_finished")
    inner = [
        e for e in events
        if e.kind not in ("agent_call_started", "agent_call_finished")
    ]

    # Framing events nest under the env-provided parent (10).
    assert started.parent_event_seq == 10
    assert finished.parent_event_seq == 10
    # Inner agent events nest under the framing started-seq, not the env parent.
    assert inner, "expected inner agent events from the stub backend"
    for ev in inner:
        assert ev.parent_event_seq == started.seq


def test_run_subagent_returns_response_cost_duration(
    run_ctx: tuple[Path, int],
) -> None:
    result = run_subagent(name="echo", prompt="anything", caller_id="caller-3")

    assert result["ok"] is True
    assert "response" in result
    assert "duration_sec" in result and result["duration_sec"] >= 0
    assert "cost_usd" in result  # may be None for stub
    assert "sub_session_id" in result
