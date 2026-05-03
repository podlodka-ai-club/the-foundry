"""Characterization tests — pin down the externally-visible behaviour of
the three real automations (``dev_task`` / ``tg_chat`` / ``pr_review``) so
upcoming refactors (kill ``AgentStage``, collapse workspace flags, extract
``runner.py``) don't silently change it.

These are coarse-grained on purpose: they exercise the **registry-level**
``Automation`` records driving a real ``Orchestrator`` against an in-memory
``StubAgent``. External commands (``git``, ``gh``, ``rsync``) and the
filesystem-bound worktree paths are stubbed so the test can run anywhere.
"""

from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from foundry.agents.base import AgentResult, AgentTask
from foundry.automations.registry import DEV_TASK, PR_REVIEW, TG_CHAT
from foundry.config import Settings
from foundry.events import dispatch_event, read_events
from foundry.models import RunStatus
from foundry.orchestrator import Orchestrator
from foundry.state import init_db, list_runs


# ---------------------------------------------------------------------------
# Fixtures: settings + stubs for external side-effects
# ---------------------------------------------------------------------------


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
        telegram_bot_token="t:token",
        pr_review_base_path=tmp_path / "umbrella",
    )


class _DoneAgent:
    """StubAgent-shaped fake that returns ``STATUS: done`` and records its
    construction-time settings + the prompt it was fed, so tests can assert
    on backend / model / prompt content."""

    name = "fake"

    def __init__(self) -> None:
        self.tasks: list[AgentTask] = []
        self.inputs: list[str] = []
        self.worktrees: list[Path] = []

    def apply(self, task: AgentTask, worktree: Path, input: str = "") -> AgentResult:
        self.tasks.append(task)
        self.inputs.append(input)
        self.worktrees.append(worktree)
        return AgentResult(
            response="Done.\n\nSTATUS: done",
            result="Done.",
        )

    def get_session_id(self, task: AgentTask) -> str | None:
        return None


@pytest.fixture
def stub_external(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Stub git/gh-bound helpers so tests are filesystem-only."""
    # worktree.ensure_base_repo / create_worktree — used by DEV_TASK.
    def _ensure_base(root: Path, _repo: str) -> Path:
        base = root / "_base"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _create_worktree(root: Path, run_id: int, _branch: str = "main") -> tuple[Path, str]:
        wt = root / f"task-{run_id}"
        wt.mkdir(parents=True, exist_ok=True)
        return wt, f"foundry/task-{run_id}"

    monkeypatch.setattr("foundry.worktree.ensure_base_repo", _ensure_base)
    monkeypatch.setattr("foundry.worktree.create_worktree", _create_worktree)

    # pr_worktree.prepare_pr_worktree — used by PR_REVIEW.
    def _prepare_pr_worktree(
        *, base_path: Path, repo: str, head_sha: str, run_id: int
    ) -> tuple[Path, str, Any]:
        wt = base_path / f"_foundry-pr-{run_id}-{repo.split('/')[-1]}"
        wt.mkdir(parents=True, exist_ok=True)
        return wt, head_sha[:12], lambda: None

    monkeypatch.setattr(
        "foundry.pr_worktree.prepare_pr_worktree", _prepare_pr_worktree
    )


async def _drive_orchestrator_until(
    orch: Orchestrator,
    *,
    expected_runs: int,
    db_path: Path,
    automation_id: str,
    timeout_sec: float = 5.0,
) -> None:
    """Spin the orchestrator loop until ``expected_runs`` runs have reached a
    terminal state for ``automation_id`` (or the timeout expires)."""
    stop = asyncio.Event()
    task = asyncio.create_task(orch.run_forever(stop))
    try:
        deadline = asyncio.get_event_loop().time() + timeout_sec
        while asyncio.get_event_loop().time() < deadline:
            runs = list_runs(db_path, automation_id=automation_id)
            terminal = [
                r
                for r in runs
                if r.status
                in (RunStatus.DONE, RunStatus.FAILED, RunStatus.UNCLEAR)
            ]
            if len(terminal) >= expected_runs:
                return
            await asyncio.sleep(0.05)
        raise AssertionError(
            f"timed out waiting for {expected_runs} terminal runs of "
            f"{automation_id!r}; got {len(list_runs(db_path, automation_id=automation_id))}"
        )
    finally:
        stop.set()
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        # Drain any in-flight `run:*` execute tasks so the next test starts
        # with a clean event loop and no orphan writers to the (closed) DB.
        pending = [
            t
            for t in asyncio.all_tasks()
            if t is not asyncio.current_task()
            and (t.get_name() or "").startswith("run:")
        ]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


# ---------------------------------------------------------------------------
# dev_task: GitHub issue → DONE, prompt loaded, worktree path under task-{id}
# ---------------------------------------------------------------------------


async def test_dev_task_event_to_done_uses_real_prompt_and_worktree(
    tmp_path: Path, stub_external: None
) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    event_id = dispatch_event(
        settings.db_path,
        trigger_id="github_issues.issue_opened",
        dedupe_key="owner/source#42",
        payload={
            "number": 42,
            "repo": "owner/source",
            "title": "Add greeting",
            "body": "Print hello on startup.",
            "labels": ["agent-task"],
        },
    )
    assert event_id is not None

    agent = _DoneAgent()
    orch = Orchestrator(settings, db_poll_sec=0.05)
    with patch("foundry.orchestrator.make_agent", return_value=agent):
        await _drive_orchestrator_until(
            orch,
            expected_runs=1,
            db_path=settings.db_path,
            automation_id=DEV_TASK.id,
        )

    runs = list_runs(settings.db_path, automation_id=DEV_TASK.id)
    assert len(runs) == 1
    assert runs[0].status is RunStatus.DONE

    # The prompt was loaded from automations/prompts/dev_task.md and the
    # event payload was interpolated.
    assert len(agent.inputs) == 1
    prompt = agent.inputs[0]
    assert "commit_and_push_pr" in prompt, "dev_task prompt must mention skill"
    assert "Add greeting" in prompt, "issue title must be interpolated"
    assert "Print hello on startup." in prompt, "issue body must be interpolated"

    # Worktree was the git_worktree variant: WORKTREE_ROOT/task-{run_id}.
    assert agent.worktrees[0] == settings.worktree_root / f"task-{runs[0].id}"


# ---------------------------------------------------------------------------
# tg_chat: two events from the same chat collapse into one session_id;
# each event still produces its own run; agent runs in the configured cwd.
# ---------------------------------------------------------------------------


async def test_tg_chat_two_messages_share_session_and_use_fixed_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stub_external: None
) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    # TG_CHAT.cwd points at the user's main project umbrella by default —
    # swap it for a tmp dir so the test doesn't depend on / mutate $HOME.
    chat_cwd = tmp_path / "tg_main"
    patched_tg = dataclasses.replace(TG_CHAT, cwd=chat_cwd)
    monkeypatch.setattr(
        "foundry.events.automations_for_trigger",
        lambda trigger_id: [patched_tg] if trigger_id == "telegram.message" else [],
    )
    # Patch both the orchestrator-side import and the registry source so the
    # test stays correct if a future refactor (e.g. extracted ``runner.py``)
    # imports ``get_automation`` from a different module path.
    monkeypatch.setattr(
        "foundry.orchestrator.get_automation",
        lambda automation_id: patched_tg if automation_id == TG_CHAT.id else None,
    )
    monkeypatch.setattr(
        "foundry.automations.registry.get_automation",
        lambda automation_id: patched_tg if automation_id == TG_CHAT.id else None,
    )

    e1 = dispatch_event(
        settings.db_path,
        trigger_id="telegram.message",
        dedupe_key="tg:1001",
        payload={"chat_id": 555, "text": "hi"},
    )
    e2 = dispatch_event(
        settings.db_path,
        trigger_id="telegram.message",
        dedupe_key="tg:1002",
        payload={"chat_id": 555, "text": "still here?"},
    )
    assert e1 is not None and e2 is not None

    agent = _DoneAgent()
    orch = Orchestrator(settings, db_poll_sec=0.05)
    with patch("foundry.orchestrator.make_agent", return_value=agent):
        await _drive_orchestrator_until(
            orch,
            expected_runs=2,
            db_path=settings.db_path,
            automation_id=TG_CHAT.id,
        )

    runs = sorted(
        list_runs(settings.db_path, automation_id=TG_CHAT.id), key=lambda r: r.id or 0
    )
    assert [r.status for r in runs] == [RunStatus.DONE, RunStatus.DONE]
    # Same chat_id → same session_id; session_seq increments.
    assert runs[0].session_id == runs[1].session_id
    assert runs[0].session_seq == 1
    assert runs[1].session_seq == 2

    # Both runs executed in the configured cwd, not the worktree root.
    assert agent.worktrees == [chat_cwd, chat_cwd]


# ---------------------------------------------------------------------------
# pr_review: two events on the same PR share a session; pr_worktree mode.
# ---------------------------------------------------------------------------


async def test_pr_review_two_events_share_session_and_use_pr_worktree(
    tmp_path: Path, stub_external: None
) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    payload_base = {
        "repo": "owner/source",
        "number": 7,
        "head_sha": "abc1234567def",
        "url": "https://github.com/owner/source/pull/7",
        "author": "alice",
    }
    e1 = dispatch_event(
        settings.db_path,
        trigger_id="github_pr_review.review_requested",
        dedupe_key="pr:owner/source#7@abc1234",
        payload=payload_base,
    )
    e2 = dispatch_event(
        settings.db_path,
        trigger_id="github_pr_review.review_requested",
        dedupe_key="pr:owner/source#7@def0000",
        payload={**payload_base, "head_sha": "def0000000abc"},
    )
    assert e1 is not None and e2 is not None

    agent = _DoneAgent()
    orch = Orchestrator(settings, db_poll_sec=0.05)
    with patch("foundry.orchestrator.make_agent", return_value=agent):
        await _drive_orchestrator_until(
            orch,
            expected_runs=2,
            db_path=settings.db_path,
            automation_id=PR_REVIEW.id,
        )

    runs = sorted(
        list_runs(settings.db_path, automation_id=PR_REVIEW.id),
        key=lambda r: r.id or 0,
    )
    assert [r.status for r in runs] == [RunStatus.DONE, RunStatus.DONE]
    # Same PR (repo+number) → same session_id, even though head_sha changed.
    assert runs[0].session_id == runs[1].session_id
    assert runs[0].session_seq == 1
    assert runs[1].session_seq == 2

    # Both runs ran inside the per-PR worktree under the umbrella.
    expected_first = settings.pr_review_base_path / f"_foundry-pr-{runs[0].id}-source"
    expected_second = settings.pr_review_base_path / f"_foundry-pr-{runs[1].id}-source"
    assert agent.worktrees == [expected_first, expected_second]


# ---------------------------------------------------------------------------
# Bonus: run_events emitted by execute_run cover the agent_input + run-stage
# lifecycle. Snapshotting kinds (not text) keeps this stable across refactors.
# ---------------------------------------------------------------------------


async def test_dev_task_run_events_kinds_snapshot(
    tmp_path: Path, stub_external: None
) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    dispatch_event(
        settings.db_path,
        trigger_id="github_issues.issue_opened",
        dedupe_key="owner/source#1",
        payload={"number": 1, "repo": "owner/source", "title": "t", "body": "b"},
    )

    orch = Orchestrator(settings, db_poll_sec=0.05)
    with patch("foundry.orchestrator.make_agent", return_value=_DoneAgent()):
        await _drive_orchestrator_until(
            orch,
            expected_runs=1,
            db_path=settings.db_path,
            automation_id=DEV_TASK.id,
        )

    runs = list_runs(settings.db_path, automation_id=DEV_TASK.id)
    assert len(runs) == 1
    events = read_events(settings.db_path, runs[0].id)
    kinds = [e.kind for e in events]
    # The exact ordering: the run-stage span wraps an agent_input event in
    # the middle. Pin both the set and the relative position.
    assert "stage_started" in kinds
    assert "agent_input" in kinds
    assert "stage_finished" in kinds
    assert kinds.index("stage_started") < kinds.index("agent_input")
    assert kinds.index("agent_input") < kinds.index("stage_finished")
