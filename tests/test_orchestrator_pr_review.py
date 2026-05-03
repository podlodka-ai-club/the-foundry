"""Coverage for the ``pr_review`` automation.

Targets:
- ``Automation.session_key`` collapses multiple events of the same PR into
  one rolling session (so the agent CLI can resume across pushes).
- ``workspace="pr_worktree"`` path goes through ``pr_worktree.prepare_pr_worktree``
  with the right args and runs the cleanup callback afterwards.
- Missing ``pr_review_base_path`` setting → run ends in FAILED/INFRA.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from foundry.agents.base import AgentResult
from foundry.automations.registry import Automation, _pr_review_session_key
from foundry.config import Settings
from foundry.events import dispatch_event
from foundry.models import Event, FailureKind, RunStatus
from foundry.orchestrator import Orchestrator
from foundry.state import create_run, get_run, init_db, list_runs


def _settings(tmp_path: Path, *, pr_base: Path | None = None) -> Settings:
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
        pr_review_base_path=pr_base,
    )


def _pr_review_automation() -> Automation:
    return Automation(
        id="pr_review",
        name="PR review",
        description="t",
        triggers=("github_pr_review.review_requested",),
        agent={"backend": "stub", "model": None},
        prompt_path="",
        workspace="pr_worktree",
        session_key=_pr_review_session_key,
    )


def _pr_event(event_id: int, *, head_sha: str) -> Event:
    return Event(
        id=event_id,
        source="github_pr_review",
        external_id=f"owner/foo#42@{head_sha}",
        kind="review_requested",
        payload={
            "repo": "owner/foo",
            "number": 42,
            "head_sha": head_sha,
            "url": "https://github.com/owner/foo/pull/42",
            "author": "bob",
            "reason": "review_requested",
        },
        created_at="2026-05-02T00:00:00+00:00",
    )


class _FakeAgent:
    name = "fake"

    def apply(self, task, worktree, input=""):
        return AgentResult(response="", result="", cost_usd=0.0)

    def get_session_id(self, task) -> str | None:
        return None


# --- session_key ---


async def test_session_key_collapses_pushes_into_same_session(
    tmp_path: Path,
) -> None:
    """Two dispatches with different ``head_sha`` but same PR get the same
    session_id — purely a dispatch-time concern, no orchestrator loop needed."""
    settings = _settings(tmp_path, pr_base=tmp_path / "umbrella")
    init_db(settings.db_path)
    auto = _pr_review_automation()

    with patch(
        "foundry.events.automations_for_trigger", return_value=[auto]
    ):
        dispatch_event(
            settings.db_path,
            trigger_id="github_pr_review.review_requested",
            dedupe_key="owner/foo#42@sha-old",
            payload={
                "repo": "owner/foo",
                "number": 42,
                "head_sha": "sha-old",
            },
        )
        dispatch_event(
            settings.db_path,
            trigger_id="github_pr_review.review_requested",
            dedupe_key="owner/foo#42@sha-new",
            payload={
                "repo": "owner/foo",
                "number": 42,
                "head_sha": "sha-new",
            },
        )

    runs = list_runs(settings.db_path, automation_id="pr_review")
    assert len(runs) == 2
    assert runs[0].session_id == runs[1].session_id
    assert {r.session_seq for r in runs} == {1, 2}


# --- pr_worktree path + cleanup ---


async def test_pr_worktree_called_with_payload_args_and_cleaned_up(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, pr_base=tmp_path / "umbrella")
    init_db(settings.db_path)
    orch = Orchestrator(settings)
    auto = _pr_review_automation()

    captured: dict[str, object] = {}
    cleanup_called = asyncio.Event()

    def fake_prepare(*, base_path, repo, head_sha, run_id):
        captured.update(
            {
                "base_path": base_path,
                "repo": repo,
                "head_sha": head_sha,
                "run_id": run_id,
            }
        )
        wt = tmp_path / f"wt-{run_id}"
        wt.mkdir(parents=True, exist_ok=True)

        def cleanup() -> None:
            cleanup_called.set()

        return wt, head_sha[:12], cleanup

    rid = create_run(
        settings.db_path,
        automation_id=auto.id,
        event_id=1,
        session_id="s",
        status=RunStatus.RUNNING,
    )
    with patch(
        "foundry.pr_worktree.prepare_pr_worktree", side_effect=fake_prepare
    ), patch("foundry.runner.make_agent", return_value=_FakeAgent()):
        await orch.execute_run(
            run_id=rid,
            automation=auto,
            event=_pr_event(1, head_sha="abc1234567890"),
            session_id="s",
        )
        await asyncio.wait_for(cleanup_called.wait(), timeout=2.0)

    assert captured["repo"] == "owner/foo"
    assert captured["head_sha"] == "abc1234567890"
    assert captured["base_path"] == settings.pr_review_base_path


# --- missing config / payload ---


async def test_missing_pr_review_base_path_fails_run_with_infra(
    tmp_path: Path,
) -> None:
    """Without PR_REVIEW_BASE_PATH the run can't materialize a worktree."""
    settings = _settings(tmp_path, pr_base=None)
    init_db(settings.db_path)
    orch = Orchestrator(settings)
    auto = _pr_review_automation()

    rid = create_run(
        settings.db_path,
        automation_id=auto.id,
        event_id=1,
        session_id="s",
        status=RunStatus.RUNNING,
    )
    with patch("foundry.runner.make_agent", return_value=_FakeAgent()):
        await orch.execute_run(
            run_id=rid,
            automation=auto,
            event=_pr_event(1, head_sha="abc"),
            session_id="s",
        )

    run = get_run(settings.db_path, rid)
    assert run is not None
    assert run.status is RunStatus.FAILED
    assert run.failure_kind is FailureKind.INFRA


# --- helper coverage ---


def test_pr_review_session_key_uses_repo_and_number() -> None:
    ev = _pr_event(1, head_sha="x")

    assert _pr_review_session_key(ev) == "pr-review:owner/foo#42"


def test_pr_review_session_key_returns_none_when_payload_incomplete() -> None:
    ev = Event(
        id=1,
        source="github_pr_review",
        external_id="x",
        kind="review_requested",
        payload={"repo": "owner/foo"},
        created_at="t",
    )

    assert _pr_review_session_key(ev) is None
