"""End-to-end integration: real ``Orchestrator.run_forever`` driving a fake
agent that returns a ``STATUS: done`` marker, proving the full
event → PENDING run → claim → execute → DONE pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from foundry.agents.base import AgentResult
from foundry.automations.registry import Automation
from foundry.config import Settings
from foundry.events import dispatch_event
from foundry.models import RunStatus
from foundry.orchestrator import Orchestrator
from foundry.state import init_db, list_runs


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


class _StatusMarkerAgent:
    """Fake agent: returns a final response containing ``STATUS: done`` —
    the orchestrator's marker parser turns the run into ``DONE``."""

    name = "fake"

    def apply(self, task, worktree, input=""):
        return AgentResult(
            response="Implemented as requested.\n\nSTATUS: done",
            result="Implemented as requested.",
            cost_usd=0.0,
            tokens_in=0,
            tokens_out=0,
        )

    def get_session_id(self, task) -> str | None:
        return None


async def test_end_to_end_event_to_done(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    fake_automation = Automation(
        id="_test",
        name="test automation",
        description="t",
        triggers=("github_issues.issue_opened",),
        agent={"backend": "stub", "model": None},
        prompt_path="",
    )

    with patch(
        "foundry.events.automations_for_trigger",
        return_value=[fake_automation],
    ):
        event_id = dispatch_event(
            settings.db_path,
            trigger_id="github_issues.issue_opened",
            dedupe_key="r#1",
            payload={
                "number": 1,
                "repo": "owner/source",
                "title": "t",
                "body": "b",
            },
        )
    assert event_id is not None

    orch = Orchestrator(settings, db_poll_sec=0.05)
    stop = asyncio.Event()

    with patch(
        "foundry.orchestrator.get_automation",
        return_value=fake_automation,
    ), patch(
        "foundry.orchestrator.make_agent", return_value=_StatusMarkerAgent()
    ):
        task = asyncio.create_task(orch.run_forever(stop))
        for _ in range(60):
            runs = list_runs(settings.db_path, automation_id="_test")
            if runs and runs[0].status is RunStatus.DONE:
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

    runs = list_runs(settings.db_path, automation_id="_test")
    assert len(runs) == 1
    assert runs[0].status is RunStatus.DONE
