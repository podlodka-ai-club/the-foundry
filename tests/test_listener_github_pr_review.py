from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from foundry.events import dispatch_event
from foundry.listeners.github_pr_review import GithubPrReviewListener
from foundry.shell import Result
from foundry.state import init_db


def _now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _old_iso(days: int) -> str:
    return (datetime.now(tz=UTC) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _pr(
    *,
    repo: str,
    number: int,
    author: str = "someone",
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "url": f"https://github.com/{repo}/pull/{number}",
        "number": number,
        "repository": {"name": repo.split("/")[1], "nameWithOwner": repo},
        "author": {"login": author, "is_bot": False, "type": "User"},
        "createdAt": created_at or _now_iso(),
        "updatedAt": _now_iso(),
    }


def _make_shell_stub(
    *,
    review_prs: list[dict[str, Any]],
    author_prs: list[dict[str, Any]],
    sha_map: dict[tuple[str, int], str],
):
    """Build a fake `shell.run` that dispatches by command shape."""

    def fn(cmd: list[str], **_kwargs: Any) -> Result:
        if "search" in cmd and "prs" in cmd:
            if any(arg.startswith("--review-requested=") for arg in cmd):
                return Result(returncode=0, stdout=json.dumps(review_prs), stderr="")
            if any(arg.startswith("--author=") for arg in cmd):
                return Result(returncode=0, stdout=json.dumps(author_prs), stderr="")
            return Result(returncode=1, stdout="", stderr="bad search")
        if cmd[:3] == ["gh", "pr", "view"]:
            number = int(cmd[3])
            repo = cmd[cmd.index("--repo") + 1]
            sha = sha_map.get((repo, number))
            if sha is None:
                return Result(returncode=1, stdout="", stderr="not found")
            return Result(
                returncode=0, stdout=json.dumps({"headRefOid": sha}), stderr=""
            )
        return Result(
            returncode=1, stdout="", stderr="unexpected: " + " ".join(cmd)
        )

    return fn


class _RecordingEmit:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        trigger_id: str,
        dedupe_key: str,
        payload: dict[str, Any],
        parent_event_id: int | None = None,
    ) -> int | None:
        self.calls.append(
            {
                "trigger_id": trigger_id,
                "dedupe_key": dedupe_key,
                "payload": payload,
            }
        )
        return len(self.calls)


async def test_tick_emits_review_requested_with_sha_in_dedupe_key() -> None:
    listener = GithubPrReviewListener(user="alice")
    emit = _RecordingEmit()
    stub = _make_shell_stub(
        review_prs=[_pr(repo="owner/foo", number=42, author="bob")],
        author_prs=[],
        sha_map={("owner/foo", 42): "abc1234"},
    )
    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub):
        await listener.tick_once(emit)

    assert len(emit.calls) == 1
    call = emit.calls[0]
    assert call["dedupe_key"] == "owner/foo#42@abc1234"
    assert call["trigger_id"] == "github_pr_review.review_requested"
    assert call["payload"]["head_sha"] == "abc1234"
    assert call["payload"]["author"] == "bob"
    assert call["payload"]["reason"] == "review_requested"


async def test_tick_emits_authored_when_only_in_author_query() -> None:
    listener = GithubPrReviewListener(user="alice")
    emit = _RecordingEmit()
    stub = _make_shell_stub(
        review_prs=[],
        author_prs=[_pr(repo="owner/foo", number=7, author="alice")],
        sha_map={("owner/foo", 7): "deadbeef"},
    )
    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub):
        await listener.tick_once(emit)

    assert len(emit.calls) == 1
    assert emit.calls[0]["trigger_id"] == "github_pr_review.authored"
    assert emit.calls[0]["payload"]["reason"] == "authored"


async def test_review_requested_wins_over_authored_on_dup() -> None:
    listener = GithubPrReviewListener(user="alice")
    emit = _RecordingEmit()
    pr = _pr(repo="owner/foo", number=42, author="alice")
    stub = _make_shell_stub(
        review_prs=[pr],
        author_prs=[pr],
        sha_map={("owner/foo", 42): "abc1234"},
    )
    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub):
        await listener.tick_once(emit)

    assert len(emit.calls) == 1
    assert emit.calls[0]["trigger_id"] == "github_pr_review.review_requested"


async def test_skip_repos_filter_substring_match() -> None:
    listener = GithubPrReviewListener(user="alice", skip_repos=("hexlet",))
    emit = _RecordingEmit()
    stub = _make_shell_stub(
        review_prs=[
            _pr(repo="hexlet/python-x", number=1),
            _pr(repo="owner/foo", number=2),
        ],
        author_prs=[],
        sha_map={("owner/foo", 2): "sha2"},
    )
    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub):
        await listener.tick_once(emit)

    assert len(emit.calls) == 1
    assert emit.calls[0]["payload"]["repo"] == "owner/foo"


async def test_max_age_days_filter_drops_old_pr() -> None:
    listener = GithubPrReviewListener(user="alice", max_age_days=30)
    emit = _RecordingEmit()
    stub = _make_shell_stub(
        review_prs=[
            _pr(repo="owner/foo", number=1, created_at=_old_iso(60)),
            _pr(repo="owner/foo", number=2, created_at=_now_iso()),
        ],
        author_prs=[],
        sha_map={("owner/foo", 2): "fresh"},
    )
    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub):
        await listener.tick_once(emit)

    assert len(emit.calls) == 1
    assert emit.calls[0]["payload"]["number"] == 2


async def test_include_authored_disabled_skips_second_query() -> None:
    listener = GithubPrReviewListener(user="alice", include_authored=False)
    emit = _RecordingEmit()
    calls: list[list[str]] = []

    def stub(cmd: list[str], **_kwargs: Any) -> Result:
        calls.append(cmd)
        if "search" in cmd and "prs" in cmd:
            return Result(returncode=0, stdout="[]", stderr="")
        return Result(returncode=1, stdout="", stderr="x")

    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub):
        await listener.tick_once(emit)

    search_calls = [c for c in calls if "search" in c and "prs" in c]
    assert len(search_calls) == 1
    assert any(arg.startswith("--review-requested=") for arg in search_calls[0])
    assert not any(arg.startswith("--author=") for arg in search_calls[0])


async def test_pr_view_failure_skips_emit() -> None:
    listener = GithubPrReviewListener(user="alice")
    emit = _RecordingEmit()
    stub = _make_shell_stub(
        review_prs=[_pr(repo="owner/foo", number=42)],
        author_prs=[],
        sha_map={},
    )
    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub):
        await listener.tick_once(emit)

    assert emit.calls == []


async def test_search_failure_keeps_listener_alive() -> None:
    listener = GithubPrReviewListener(user="alice")
    emit = _RecordingEmit()

    def stub(cmd: list[str], **_kwargs: Any) -> Result:
        return Result(returncode=1, stdout="", stderr="rate limited")

    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub):
        await listener.tick_once(emit)

    assert emit.calls == []


async def test_dedup_through_db_two_ticks_same_sha(tmp_path: Path) -> None:
    db_path = tmp_path / "ev.sqlite"
    init_db(db_path)
    listener = GithubPrReviewListener(user="alice")

    async def emit(*, trigger_id, dedupe_key, payload, parent_event_id=None):
        return dispatch_event(
            db_path,
            trigger_id=trigger_id,
            dedupe_key=dedupe_key,
            payload=payload,
            parent_event_id=parent_event_id,
        )

    stub = _make_shell_stub(
        review_prs=[_pr(repo="owner/foo", number=42)],
        author_prs=[],
        sha_map={("owner/foo", 42): "abc1234"},
    )
    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub):
        await listener.tick_once(emit)
        await listener.tick_once(emit)

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 1


async def test_dedup_two_ticks_new_sha_emits_again(tmp_path: Path) -> None:
    db_path = tmp_path / "ev.sqlite"
    init_db(db_path)
    listener = GithubPrReviewListener(user="alice")

    async def emit(*, trigger_id, dedupe_key, payload, parent_event_id=None):
        return dispatch_event(
            db_path,
            trigger_id=trigger_id,
            dedupe_key=dedupe_key,
            payload=payload,
            parent_event_id=parent_event_id,
        )

    pr_data = [_pr(repo="owner/foo", number=42)]
    stub_first = _make_shell_stub(
        review_prs=pr_data, author_prs=[], sha_map={("owner/foo", 42): "sha-old"}
    )
    stub_second = _make_shell_stub(
        review_prs=pr_data, author_prs=[], sha_map={("owner/foo", 42): "sha-new"}
    )
    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub_first):
        await listener.tick_once(emit)
    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub_second):
        await listener.tick_once(emit)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT external_id FROM events ORDER BY id"
        ).fetchall()
    assert [r[0] for r in rows] == [
        "owner/foo#42@sha-old",
        "owner/foo#42@sha-new",
    ]


async def test_empty_results_handled() -> None:
    listener = GithubPrReviewListener(user="alice")
    emit = _RecordingEmit()
    stub = _make_shell_stub(review_prs=[], author_prs=[], sha_map={})
    with patch("foundry.listeners.github_pr_review.shell.run", side_effect=stub):
        await listener.tick_once(emit)

    assert emit.calls == []
