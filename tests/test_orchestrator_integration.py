"""End-to-end integration: real `Orchestrator.run_forever` driving a fake
agent that calls `mark_done_impl()` directly (no MCP subprocess), proving
the full event → run → status=DONE pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry.agents.base import AgentResult, AgentStage
from foundry.automations.registry import Automation
from foundry.config import Settings
from foundry.models import RunStatus
from foundry.orchestrator import Orchestrator
from foundry.skills.run_lifecycle import mark_done_impl
from foundry.state import init_db, list_runs, record_external_event


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        source_repo="owner/source",
        target_repo="owner/target",
        issue_label="agent-task",
        worktree_root=tmp_path / "wt",
        db_path=tmp_path / "f.sqlite",
        poll_interval_seconds=30,
        github_token=None,
        max_implement_attempts=2,
        listeners_enabled=(),
        github_poll_sec=30,
    )


class _MarkDoneAgent:
    """Fake agent: simulates a top-level agent that calls mark_done at the
    end of its turn. Reads env that the orchestrator's MCP-config-shaped
    extra_env would normally provide to the subprocess — but here we pull
    them straight from os.environ and the agent_settings.mcp_config file
    is ignored.

    The orchestrator does NOT export those env vars to the current process
    (they go into the per-run mcp config file for the would-be subprocess),
    so this fake agent monkeys them in itself based on the task id passed
    in.
    """

    name = "fake"
    stage = AgentStage.IMPLEMENT

    def __init__(self, settings, db_path: Path) -> None:
        self._settings = settings
        self._db_path = db_path

    def apply(self, task, worktree, input=""):
        import os

        run_id = task.id
        old_db = os.environ.get("FOUNDRY_DB_PATH")
        old_run = os.environ.get("FOUNDRY_RUN_ID")
        os.environ["FOUNDRY_DB_PATH"] = str(self._db_path)
        os.environ["FOUNDRY_RUN_ID"] = str(run_id)
        try:
            out = mark_done_impl()
            assert out["ok"]
        finally:
            if old_db is None:
                os.environ.pop("FOUNDRY_DB_PATH", None)
            else:
                os.environ["FOUNDRY_DB_PATH"] = old_db
            if old_run is None:
                os.environ.pop("FOUNDRY_RUN_ID", None)
            else:
                os.environ["FOUNDRY_RUN_ID"] = old_run

        return AgentResult(
            stage=self.stage,
            response="done",
            result="done",
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
        triggers=("github_issues",),
        agent={"backend": "stub", "model": None},
        prompt_path="",
        skills=("mark_done",),
    )

    def _make_fake_agent(agent_settings):
        return _MarkDoneAgent(agent_settings, settings.db_path)

    event_id = record_external_event(
        settings.db_path,
        source="github_issues",
        external_id="r#1",
        kind="issue.opened",
        payload={"number": 1, "repo": "owner/source", "title": "t", "body": "b"},
    )
    assert event_id is not None

    orch = Orchestrator(settings, db_poll_sec=0.05)
    stop = asyncio.Event()

    with patch(
        "foundry.orchestrator.automations_for_trigger",
        return_value=[fake_automation],
    ), patch("foundry.orchestrator.make_agent", side_effect=_make_fake_agent):
        task = asyncio.create_task(orch.run_forever(stop))
        # Wait until run shows up + reaches a terminal state.
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
