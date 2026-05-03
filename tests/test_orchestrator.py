"""Tests for the post-refactor orchestrator (single PENDING-queue path).

The orchestrator no longer has a separate ``handle_event`` path or an event
cursor. Listeners enqueue work via ``dispatch_event`` (which inserts the
event AND a ``PENDING`` run for every subscribed automation in one
transaction). The orchestrator atomically claims PENDING rows and executes
them.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from foundry.agents.base import AgentResult
from foundry.automations.registry import Automation
from foundry.config import Settings
from foundry.events import dispatch_event, read_events
from foundry.models import Event, RunStatus
from foundry.orchestrator import Orchestrator, _load_automation_prompt
from foundry.state import (
    create_run,
    get_run,
    init_db,
    list_runs,
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
    triggers_: tuple[str, ...] = ("github_issues.issue_opened",),
    backend: str = "stub",
    git_worktree: bool = False,
) -> Automation:
    return Automation(
        id=aid,
        name=f"test:{aid}",
        description="t",
        triggers=triggers_,
        agent={"backend": backend, "model": None},
        prompt_path="",
        git_worktree=git_worktree,
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

    def __init__(self, *, response: str = "ok", session_id: str | None = "fake-sess") -> None:
        self._response = response
        self._session_id = session_id

    def apply(self, task, worktree, input=""):
        return AgentResult(
            response=self._response,
            result=self._response.splitlines()[0] if self._response else "",
            cost_usd=0.001,
            tokens_in=10,
            tokens_out=20,
        )

    def get_session_id(self, task) -> str | None:
        return self._session_id


# --- dispatch + claim path ---


async def test_dispatch_creates_pending_run_per_subscribed_automation(
    tmp_path: Path,
) -> None:
    """``dispatch_event`` writes ``PENDING`` rows synchronously — one per
    subscribed automation."""
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    a1 = _automation(aid="a1")
    a2 = _automation(aid="a2")
    with patch(
        "foundry.events.automations_for_trigger", return_value=[a1, a2]
    ):
        eid = dispatch_event(
            settings.db_path,
            trigger_id="github_issues.issue_opened",
            dedupe_key="repo#1",
            payload={"number": 1, "title": "t", "body": "b"},
        )
    assert eid is not None

    runs = list_runs(settings.db_path, status=RunStatus.PENDING)
    assert {r.automation_id for r in runs} == {"a1", "a2"}


async def test_dispatch_skips_when_no_subscribed_automations(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    with patch("foundry.events.automations_for_trigger", return_value=[]):
        eid = dispatch_event(
            settings.db_path,
            trigger_id="github_issues.issue_opened",
            dedupe_key="repo#1",
            payload={"number": 1},
        )
    assert eid is not None
    assert list_runs(settings.db_path) == []


async def test_dispatch_dedup_does_not_duplicate_runs(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    auto = _automation(aid="a")
    with patch(
        "foundry.events.automations_for_trigger", return_value=[auto]
    ):
        first = dispatch_event(
            settings.db_path,
            trigger_id="github_issues.issue_opened",
            dedupe_key="repo#1",
            payload={"number": 1},
        )
        second = dispatch_event(
            settings.db_path,
            trigger_id="github_issues.issue_opened",
            dedupe_key="repo#1",
            payload={"number": 1},
        )
    assert isinstance(first, int)
    assert second is None
    assert len(list_runs(settings.db_path)) == 1


# --- run_forever + execute ---


async def test_run_forever_drains_pending_queue(tmp_path: Path) -> None:
    """End-to-end: dispatch → orchestrator claims PENDING → executes."""
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    auto = _automation(aid="picked")

    with patch(
        "foundry.events.automations_for_trigger", return_value=[auto]
    ), patch(
        "foundry.orchestrator.get_automation", return_value=auto
    ), patch("foundry.orchestrator.make_agent", return_value=_FakeAgent()):
        dispatch_event(
            settings.db_path,
            trigger_id="github_issues.issue_opened",
            dedupe_key="repo#1",
            payload={"number": 1, "title": "t", "body": "b"},
        )

        orch = Orchestrator(settings, db_poll_sec=0.05)
        stop = asyncio.Event()
        orch.wake.set()  # wake immediately
        task = asyncio.create_task(orch.run_forever(stop))
        for _ in range(60):
            runs = list_runs(settings.db_path, automation_id="picked")
            if runs and runs[0].status is not RunStatus.PENDING and runs[0].status is not RunStatus.RUNNING:
                break
            await asyncio.sleep(0.05)
        stop.set()
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    runs = list_runs(settings.db_path, automation_id="picked")
    assert len(runs) == 1
    # Agent did not call mark_done → UNCLEAR (per execute_run contract).
    assert runs[0].status is RunStatus.UNCLEAR


async def test_run_forever_recovers_orphan_running_on_start(
    tmp_path: Path,
) -> None:
    """A RUNNING row at startup means the previous process died — recovery
    flips it to FAILED/INFRA before claiming new work."""
    from foundry.models import FailureKind

    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orphan = create_run(
        settings.db_path,
        automation_id="a",
        event_id=1,
        session_id="s",
        status=RunStatus.RUNNING,
    )

    orch = Orchestrator(settings, db_poll_sec=0.05)
    stop = asyncio.Event()
    task = asyncio.create_task(orch.run_forever(stop))
    await asyncio.sleep(0.1)
    stop.set()
    try:
        await asyncio.wait_for(task, timeout=1.0)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    run = get_run(settings.db_path, orphan)
    assert run is not None
    assert run.status is RunStatus.FAILED
    assert run.failure_kind is FailureKind.INFRA


async def test_claim_finalizes_run_when_automation_missing(
    tmp_path: Path,
) -> None:
    """Regression: a PENDING run whose automation is no longer registered
    must be finalized as FAILED/INFRA, not left in RUNNING."""
    from foundry.models import FailureKind

    settings = _settings(tmp_path)
    init_db(settings.db_path)

    # Insert event + a PENDING run referencing an unregistered automation.
    auto = _automation(aid="vanished")
    with patch(
        "foundry.events.automations_for_trigger", return_value=[auto]
    ):
        dispatch_event(
            settings.db_path,
            trigger_id="github_issues.issue_opened",
            dedupe_key="x#1",
            payload={"number": 1},
        )

    # `get_automation` returns None — automation deregistered.
    with patch("foundry.orchestrator.get_automation", return_value=None):
        orch = Orchestrator(settings, db_poll_sec=0.05)
        stop = asyncio.Event()
        orch.wake.set()
        task = asyncio.create_task(orch.run_forever(stop))
        for _ in range(50):
            runs = list_runs(settings.db_path)
            if runs and runs[0].status is not RunStatus.PENDING and runs[0].status is not RunStatus.RUNNING:
                break
            await asyncio.sleep(0.05)
        stop.set()
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    runs = list_runs(settings.db_path)
    assert len(runs) == 1
    assert runs[0].status is RunStatus.FAILED
    assert runs[0].failure_kind is FailureKind.INFRA


async def test_execute_run_writes_stage_started_finished_events(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)
    auto = _automation(aid="a")

    rid = create_run(
        settings.db_path,
        automation_id=auto.id,
        event_id=1,
        session_id="s",
        status=RunStatus.RUNNING,
    )
    with patch("foundry.orchestrator.make_agent", return_value=_FakeAgent()):
        await orch.execute_run(
            run_id=rid, automation=auto, event=_event(1), session_id="s"
        )

    events = read_events(settings.db_path, run_id=rid)
    kinds = {(e.stage, e.kind) for e in events}
    assert ("run", "stage_started") in kinds
    assert ("run", "stage_finished") in kinds


async def test_execute_run_unclear_when_agent_did_not_mark_done(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)
    auto = _automation(aid="a")

    rid = create_run(
        settings.db_path,
        automation_id=auto.id,
        event_id=1,
        session_id="s",
        status=RunStatus.RUNNING,
    )
    with patch("foundry.orchestrator.make_agent", return_value=_FakeAgent()):
        await orch.execute_run(
            run_id=rid, automation=auto, event=_event(1), session_id="s"
        )

    run = get_run(settings.db_path, rid)
    assert run is not None
    assert run.status is RunStatus.UNCLEAR


async def test_execute_run_failed_with_infra_kind_on_exception(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    orch = Orchestrator(settings)
    auto = _automation(aid="a")

    class _BoomAgent(_FakeAgent):
        def apply(self, task, worktree, input=""):
            raise RuntimeError("boom")

    rid = create_run(
        settings.db_path,
        automation_id=auto.id,
        event_id=1,
        session_id="s",
        status=RunStatus.RUNNING,
    )
    with patch("foundry.orchestrator.make_agent", return_value=_BoomAgent()):
        await orch.execute_run(
            run_id=rid, automation=auto, event=_event(1), session_id="s"
        )

    run = get_run(settings.db_path, rid)
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

    rid = create_run(
        settings.db_path,
        automation_id=auto.id,
        event_id=1,
        session_id="s",
        status=RunStatus.RUNNING,
    )
    with patch(
        "foundry.orchestrator.make_agent",
        return_value=_FakeAgent(session_id="sess-9"),
    ):
        await orch.execute_run(
            run_id=rid, automation=auto, event=_event(1), session_id="s"
        )

    run = get_run(settings.db_path, rid)
    assert run is not None
    assert run.agent_session_id == "sess-9"


# --- prompt rendering helpers ---


def test_load_automation_prompt_falls_back_to_description() -> None:
    auto = _automation(aid="a")
    ev = _event(1)

    assert _load_automation_prompt(auto, ev) == auto.description


def test_load_automation_prompt_resume_telegram_returns_only_text() -> None:
    auto = _automation(aid="tg_chat")
    ev = Event(
        id=99,
        source="telegram",
        external_id="tg-1-99",
        kind="message",
        payload={"chat_id": 1, "text": "АУ?", "first_name": "M"},
        created_at="t",
    )

    assert _load_automation_prompt(auto, ev, resuming=True) == "АУ?"


def test_load_automation_prompt_fresh_telegram_renders_template() -> None:
    auto = _automation(aid="tg_chat")
    ev = Event(
        id=99,
        source="telegram",
        external_id="tg-1-99",
        kind="message",
        payload={"chat_id": 1, "text": "АУ?", "first_name": "M"},
        created_at="t",
    )

    assert _load_automation_prompt(auto, ev, resuming=False) == auto.description


def test_load_automation_prompt_resume_non_telegram_still_renders() -> None:
    auto = _automation(aid="dev_task")
    ev = _event(1, source="github_issues", payload={"number": 7, "body": "B"})

    assert _load_automation_prompt(auto, ev, resuming=True) == auto.description
