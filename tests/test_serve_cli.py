from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from foundry.cli import _make_emit, _supervise, main
from foundry.config import Settings
from foundry.listeners import build_listeners
from foundry.listeners.base import EmitFn
from foundry.state import init_db


def _settings(
    tmp_path: Path,
    *,
    listeners_enabled: tuple[str, ...] = (),
) -> Settings:
    return Settings(
        source_repo="owner/repo",
        target_repo="owner/repo",
        issue_label="agent-task",
        worktree_root=tmp_path / "wt",
        db_path=tmp_path / "foundry.sqlite",
        poll_interval_seconds=30,
        github_token=None,
        max_implement_attempts=2,
        listeners_enabled=listeners_enabled,
        github_poll_sec=30,
    )


def test_serve_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["serve", "--help"])

    assert result.exit_code == 0
    assert "daemon" in result.output.lower() or "listener" in result.output.lower()


def test_build_listeners_empty_filter_returns_all(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    listeners = build_listeners(settings)

    assert len(listeners) == 3
    assert {l.id for l in listeners} == {"github_issues", "cron", "discord"}


def test_build_listeners_filter_by_id(tmp_path: Path) -> None:
    settings = _settings(tmp_path, listeners_enabled=("cron",))

    listeners = build_listeners(settings)

    assert len(listeners) == 1
    assert listeners[0].id == "cron"


async def test_supervise_stops_on_event(tmp_path: Path) -> None:
    db_path = tmp_path / "ev.sqlite"
    init_db(db_path)

    class _SleepyListener:
        id = "sleepy"
        source = "sleepy"

        async def listen(self, emit: EmitFn) -> None:
            await asyncio.sleep(10.0)

    stop = asyncio.Event()
    task = asyncio.create_task(_supervise(_SleepyListener(), db_path, stop))

    # Let the listener actually start before cancelling.
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=0.5)


async def test_make_emit_writes_to_db(tmp_path: Path) -> None:
    db_path = tmp_path / "ev.sqlite"
    init_db(db_path)

    emit = _make_emit("github_issues", db_path)

    event_id = await emit(
        external_id="owner/repo#1",
        kind="issue.opened",
        payload={"title": "x"},
    )

    assert event_id == 1
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT source, external_id, kind FROM events WHERE id = 1"
        ).fetchone()
    assert row == ("github_issues", "owner/repo#1", "issue.opened")


async def test_make_emit_hints_orchestrator_on_new_event(tmp_path: Path) -> None:
    db_path = tmp_path / "ev.sqlite"
    init_db(db_path)

    hinted: list[int] = []

    class _OrchStub:
        def hint(self, event_id: int) -> None:
            hinted.append(event_id)

    emit = _make_emit("github_issues", db_path, _OrchStub())

    event_id = await emit(
        external_id="owner/repo#10",
        kind="issue.opened",
        payload={"title": "x"},
    )

    assert event_id is not None
    assert hinted == [event_id]


async def test_make_emit_does_not_hint_on_dedup(tmp_path: Path) -> None:
    db_path = tmp_path / "ev.sqlite"
    init_db(db_path)

    hinted: list[int] = []

    class _OrchStub:
        def hint(self, event_id: int) -> None:
            hinted.append(event_id)

    emit = _make_emit("github_issues", db_path, _OrchStub())

    first = await emit(
        external_id="owner/repo#11",
        kind="issue.opened",
        payload={"title": "x"},
    )
    second = await emit(
        external_id="owner/repo#11",
        kind="issue.opened",
        payload={"title": "x"},
    )

    assert first is not None
    assert second is None  # dedupe path returns None
    assert hinted == [first]
