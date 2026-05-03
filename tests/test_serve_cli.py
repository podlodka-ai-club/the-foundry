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
        listeners_enabled=listeners_enabled,
        github_poll_sec=30,
    )


def test_serve_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["serve", "--help"])

    assert result.exit_code == 0
    assert "daemon" in result.output.lower() or "listener" in result.output.lower()


def test_runs_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["runs", "--help"])

    assert result.exit_code == 0
    assert "runs" in result.output.lower()


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
    wake = asyncio.Event()
    task = asyncio.create_task(
        _supervise(_SleepyListener(), db_path, stop, wake)
    )

    # Let the listener actually start before cancelling.
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=0.5)


async def test_make_emit_writes_to_db_via_dispatch(tmp_path: Path) -> None:
    db_path = tmp_path / "ev.sqlite"
    init_db(db_path)
    wake = asyncio.Event()

    emit = _make_emit(db_path, wake)

    event_id = await emit(
        trigger_id="github_issues.issue_opened",
        dedupe_key="owner/repo#1",
        payload={"title": "x"},
    )

    assert event_id == 1
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT trigger_id, source, external_id, kind FROM events WHERE id = 1"
        ).fetchone()
    assert row == (
        "github_issues.issue_opened",
        "github_issues",
        "owner/repo#1",
        "issue_opened",
    )


async def test_make_emit_sets_wake_on_new_event(tmp_path: Path) -> None:
    db_path = tmp_path / "ev.sqlite"
    init_db(db_path)
    wake = asyncio.Event()

    emit = _make_emit(db_path, wake)
    event_id = await emit(
        trigger_id="github_issues.issue_opened",
        dedupe_key="owner/repo#10",
        payload={"title": "x"},
    )

    assert event_id is not None
    assert wake.is_set()


async def test_make_emit_does_not_wake_on_dedup(tmp_path: Path) -> None:
    db_path = tmp_path / "ev.sqlite"
    init_db(db_path)
    wake = asyncio.Event()

    emit = _make_emit(db_path, wake)

    first = await emit(
        trigger_id="github_issues.issue_opened",
        dedupe_key="owner/repo#11",
        payload={"title": "x"},
    )
    wake.clear()
    second = await emit(
        trigger_id="github_issues.issue_opened",
        dedupe_key="owner/repo#11",
        payload={"title": "x"},
    )

    assert first is not None
    assert second is None  # dedupe path returns None
    assert not wake.is_set()
