from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry.agents.base import AgentResult, AgentStage
from foundry.automations.registry import Automation
from foundry.config import Settings
from foundry.events import read_events
from foundry.models import Event, RunStatus
from foundry.orchestrator import (
    Orchestrator,
    _load_automation_prompt,
    _trigger_ids_for_event,
)
from foundry.state import (
    create_run,
    get_orchestrator_cursor,
    get_run,
    init_db,
    list_runs,
    record_external_event,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        source_repo="owner/source",
        target_repo="owner/target",
        issue_label="agent-task",
        worktree_root=tmp_path / "wt",
        db_path=tmp_path / "f.sqlite",
        poll_interval_seconds=30,
        github_token=None,
        listeners_enabled=(),
        github_poll_sec=30,
    )


def _automation(
    *,
    aid: str = "test",
    triggers: tuple[str, ...] = ("github_issues",),
    skills: tuple[str, ...] = (),
    backend: str = "stub",
) -> Automation:
    return Automation(
        id=aid,
        name=f"test:{aid}",
        description="t",
        triggers=triggers,
        agent={"backend": backend, "model": None},
        prompt_path="",
        skills=skills,
    )


def _event(event_id: int = 1, *, source: str = "github_issues", payload: dict | None = None) -> Event:
    return Event(
        id=event_id,
        source=source,
        external_id=f"{source}#{event_id}",
        kind="issue.opened",
        payload=payload or {"number": 1, "title": "t", "body": "b"},
        created_at="2026-01-01T00:00:00+00:00",
    )


class _FakeAgent:
    """Minimal CodingAgent stub for orchestrator unit tests."""

    name = "fake"
    stage = AgentStage.IMPLEMENT

    def __init__(self, *, response: str = "ok", session_id: str | None = "fake-sess") -> None:
        self._response = response
        self._session_id = session_id

    def apply(self, task, worktree, input=""):
        return AgentResult(
            stage=self.stage,
            response=self._response,
            result=self._response.splitlines()[0] if self._response else "",
            cost_usd=0.001,
            tokens_in=10,
            tokens_out=20,
        )

    def get_session_id(self, task) -> str | None:
        return self._session_id


# --- handle_event ---


async def test_handle_event_finds_subscribed_automations(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)

    auto = _automation()
    with patch(
        "foundry.orchestrator.automations_for_trigger", return_value=[auto]
    ), patch("foundry.orchestrator.make_agent", return_value=_FakeAgent()):
        run_ids = await orch.handle_event(_event(1))

    # We let execute_run finish in the background.
    await asyncio.sleep(0.05)
    assert len(run_ids) == 1


async def test_handle_event_skips_unmatched_trigger(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)

    with patch("foundry.orchestrator.automations_for_trigger", return_value=[]):
        run_ids = await orch.handle_event(_event(1))

    assert run_ids == []


async def test_handle_event_creates_run_per_automation(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)

    a1 = _automation(aid="a1")
    a2 = _automation(aid="a2")
    with patch(
        "foundry.orchestrator.automations_for_trigger", return_value=[a1, a2]
    ), patch("foundry.orchestrator.make_agent", return_value=_FakeAgent()):
        run_ids = await orch.handle_event(_event(1))

    await asyncio.sleep(0.05)
    assert len(run_ids) == 2
    assert len(set(run_ids)) == 2


async def test_handle_event_skips_when_running_run_exists(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)

    # Pre-create a running run for (event_id=1, automation_id="dup").
    create_run(
        settings.db_path,
        automation_id="dup",
        event_id=1,
        session_id="s",
        status=RunStatus.RUNNING,
    )

    auto = _automation(aid="dup")
    with patch(
        "foundry.orchestrator.automations_for_trigger", return_value=[auto]
    ), patch("foundry.orchestrator.make_agent", return_value=_FakeAgent()):
        run_ids = await orch.handle_event(_event(1))

    assert run_ids == []


# --- execute_run ---


async def test_execute_run_writes_stage_started_finished_events(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)
    auto = _automation(aid="a")

    with patch("foundry.orchestrator.make_agent", return_value=_FakeAgent()):
        run_id = await orch._create_and_dispatch(_event(1), auto)
        # Wait for the fire-and-forget execute_run to complete.
        for _ in range(50):
            run = get_run(settings.db_path, run_id)
            if run and run.status is not RunStatus.RUNNING:
                break
            await asyncio.sleep(0.05)

    events = read_events(settings.db_path, run_id=run_id)
    kinds = {(e.stage, e.kind) for e in events}
    assert ("run", "stage_started") in kinds
    assert ("run", "stage_finished") in kinds


async def test_execute_run_unclear_when_agent_did_not_mark_done(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)
    auto = _automation(aid="a")

    with patch("foundry.orchestrator.make_agent", return_value=_FakeAgent()):
        run_id = await orch._create_and_dispatch(_event(1), auto)
        for _ in range(50):
            run = get_run(settings.db_path, run_id)
            if run and run.status is not RunStatus.RUNNING:
                break
            await asyncio.sleep(0.05)

    run = get_run(settings.db_path, run_id)
    assert run is not None
    assert run.status is RunStatus.UNCLEAR


async def test_execute_run_failed_with_infra_kind_on_exception(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)
    auto = _automation(aid="a")

    class _BoomAgent(_FakeAgent):
        def apply(self, task, worktree, input=""):
            raise RuntimeError("boom")

    with patch("foundry.orchestrator.make_agent", return_value=_BoomAgent()):
        run_id = await orch._create_and_dispatch(_event(1), auto)
        for _ in range(50):
            run = get_run(settings.db_path, run_id)
            if run and run.status is not RunStatus.RUNNING:
                break
            await asyncio.sleep(0.05)

    run = get_run(settings.db_path, run_id)
    assert run is not None
    assert run.status is RunStatus.FAILED
    assert run.failure_kind is not None
    assert run.failure_kind.value == "infra"
    assert run.failure_msg and "boom" in run.failure_msg


async def test_execute_run_persists_agent_session_id(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)
    auto = _automation(aid="a")

    with patch(
        "foundry.orchestrator.make_agent",
        return_value=_FakeAgent(session_id="sess-9"),
    ):
        run_id = await orch._create_and_dispatch(_event(1), auto)
        for _ in range(50):
            run = get_run(settings.db_path, run_id)
            if run and run.status is not RunStatus.RUNNING:
                break
            await asyncio.sleep(0.05)

    run = get_run(settings.db_path, run_id)
    assert run is not None
    assert run.agent_session_id == "sess-9"


# --- run_forever cursor / queue ---


async def test_run_forever_advances_cursor(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    eid_a = record_external_event(
        settings.db_path,
        source="github_issues",
        external_id="x#1",
        kind="issue.opened",
        payload={"number": 1, "title": "t", "body": "b"},
    )
    eid_b = record_external_event(
        settings.db_path,
        source="github_issues",
        external_id="x#2",
        kind="issue.opened",
        payload={"number": 2, "title": "t", "body": "b"},
    )

    orch = Orchestrator(settings, db_poll_sec=0.05)
    stop = asyncio.Event()

    with patch("foundry.orchestrator.automations_for_trigger", return_value=[]):
        task = asyncio.create_task(orch.run_forever(stop))
        await asyncio.sleep(0.3)
        stop.set()
        await asyncio.wait_for(task, timeout=1.0)

    cursor = get_orchestrator_cursor(settings.db_path)
    assert cursor >= max(eid_a or 0, eid_b or 0)


async def test_run_forever_drains_queue_hints(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings, db_poll_sec=10.0)

    record_external_event(
        settings.db_path,
        source="github_issues",
        external_id="x#1",
        kind="issue.opened",
        payload={"number": 1, "title": "t", "body": "b"},
    )

    stop = asyncio.Event()
    auto = _automation(aid="hinted")
    with patch(
        "foundry.orchestrator.automations_for_trigger", return_value=[auto]
    ), patch("foundry.orchestrator.make_agent", return_value=_FakeAgent()):
        task = asyncio.create_task(orch.run_forever(stop))
        await asyncio.sleep(0.05)
        # Hint should wake run_forever before db_poll_sec elapses.
        orch.hint(1)
        # Give it time to dispatch and execute_run to start.
        for _ in range(50):
            runs = list_runs(settings.db_path, automation_id="hinted")
            if runs:
                break
            await asyncio.sleep(0.05)
        stop.set()
        # Allow shutdown — run_forever waits up to db_poll_sec on queue.get().
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    runs = list_runs(settings.db_path, automation_id="hinted")
    assert len(runs) == 1


async def test_pickup_fails_pending_run_when_automation_missing(
    tmp_path: Path,
) -> None:
    """Regression: PENDING runs whose automation is no longer registered
    must be finalized as FAILED/INFRA, not left hanging in RUNNING."""
    from foundry.models import FailureKind

    settings = _settings(tmp_path)
    init_db(settings.db_path)

    eid = record_external_event(
        settings.db_path,
        source="github_issues",
        external_id="x#1",
        kind="issue.opened",
        payload={"number": 1},
    )
    assert eid is not None

    rid = create_run(
        settings.db_path,
        automation_id="vanished",  # not in registry
        event_id=eid,
        session_id="abc",
        session_seq=1,
        status=RunStatus.PENDING,
    )

    orch = Orchestrator(settings, db_poll_sec=0.05)
    stop = asyncio.Event()
    task = asyncio.create_task(orch.run_forever(stop))
    await asyncio.sleep(0.2)
    stop.set()
    try:
        await asyncio.wait_for(task, timeout=1.0)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    run = get_run(settings.db_path, rid)
    assert run is not None
    assert run.status is RunStatus.FAILED
    assert run.failure_kind is FailureKind.INFRA


# --- helpers ---


def test_trigger_ids_cron_extracts_rule_id() -> None:
    ev = Event(
        id=1,
        source="cron",
        external_id="cron-hourly-2026-01-01",
        kind="tick",
        payload={"rule_id": "hourly"},
        created_at="t",
    )

    assert _trigger_ids_for_event(ev) == ["cron:hourly"]


def test_trigger_ids_non_cron_uses_source() -> None:
    ev = Event(
        id=1, source="github_issues", external_id="x", kind="k", payload={}, created_at="t"
    )

    assert _trigger_ids_for_event(ev) == ["github_issues"]


def test_load_automation_prompt_falls_back_to_description() -> None:
    auto = _automation(aid="a")
    ev = _event(1)

    assert _load_automation_prompt(auto, ev) == auto.description
