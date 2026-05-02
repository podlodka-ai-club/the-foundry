from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from foundry.listeners.github_issues import GithubIssuesListener
from foundry.shell import Result
from foundry.state import init_db, record_external_event


def _gh_result(issues: list[dict[str, Any]]) -> Result:
    return Result(returncode=0, stdout=json.dumps(issues), stderr="")


class _RecordingEmit:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        external_id: str,
        kind: str,
        payload: dict[str, Any],
        parent_event_id: int | None = None,
    ) -> int | None:
        self.calls.append(
            {
                "external_id": external_id,
                "kind": kind,
                "payload": payload,
                "parent_event_id": parent_event_id,
            }
        )
        return len(self.calls)


async def test_tick_once_emits_each_issue() -> None:
    issues = [
        {
            "number": 1,
            "title": "first",
            "body": "body1",
            "labels": [{"name": "agent-task", "color": "x"}],
            "createdAt": "2026-05-01T00:00:00Z",
            "updatedAt": "2026-05-01T01:00:00Z",
        },
        {
            "number": 2,
            "title": "second",
            "body": "body2",
            "labels": [],
            "createdAt": "2026-05-02T00:00:00Z",
            "updatedAt": "2026-05-02T01:00:00Z",
        },
    ]
    listener = GithubIssuesListener(repo="owner/repo", label="agent-task")
    emit = _RecordingEmit()

    with patch(
        "foundry.listeners.github_issues.shell.run",
        return_value=_gh_result(issues),
    ):
        await listener.tick_once(emit)

    assert len(emit.calls) == 2
    assert emit.calls[0]["kind"] == "issue.opened"
    assert emit.calls[0]["payload"]["title"] == "first"
    assert emit.calls[1]["payload"]["number"] == 2


async def test_tick_once_external_id_format() -> None:
    issues = [
        {
            "number": 42,
            "title": "x",
            "body": "",
            "labels": [],
            "createdAt": "x",
            "updatedAt": "x",
        }
    ]
    listener = GithubIssuesListener(repo="owner/repo", label="agent-task")
    emit = _RecordingEmit()

    with patch(
        "foundry.listeners.github_issues.shell.run",
        return_value=_gh_result(issues),
    ):
        await listener.tick_once(emit)

    assert emit.calls[0]["external_id"] == "owner/repo#42"


async def test_tick_handles_empty_list() -> None:
    listener = GithubIssuesListener(repo="owner/repo", label="agent-task")
    emit = _RecordingEmit()

    with patch(
        "foundry.listeners.github_issues.shell.run",
        return_value=_gh_result([]),
    ):
        await listener.tick_once(emit)

    assert emit.calls == []


async def test_tick_dedup_via_emit_with_real_db(tmp_path: Path) -> None:
    db_path = tmp_path / "ev.sqlite"
    init_db(db_path)

    issues = [
        {
            "number": 1,
            "title": "one",
            "body": "",
            "labels": [],
            "createdAt": "x",
            "updatedAt": "x",
        },
        {
            "number": 2,
            "title": "two",
            "body": "",
            "labels": [],
            "createdAt": "x",
            "updatedAt": "x",
        },
    ]
    listener = GithubIssuesListener(repo="owner/repo", label="agent-task")

    async def emit(*, external_id, kind, payload, parent_event_id=None):
        return record_external_event(
            db_path,
            source=listener.source,
            external_id=external_id,
            kind=kind,
            payload=payload,
            parent_event_id=parent_event_id,
        )

    with patch(
        "foundry.listeners.github_issues.shell.run",
        return_value=_gh_result(issues),
    ):
        await listener.tick_once(emit)
        await listener.tick_once(emit)

    import sqlite3

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 2


async def test_tick_flattens_labels() -> None:
    issues = [
        {
            "number": 1,
            "title": "x",
            "body": "",
            "labels": [
                {"name": "agent-task", "color": "x"},
                {"name": "bug", "color": "y"},
            ],
            "createdAt": "x",
            "updatedAt": "x",
        }
    ]
    listener = GithubIssuesListener(repo="owner/repo", label="agent-task")
    emit = _RecordingEmit()

    with patch(
        "foundry.listeners.github_issues.shell.run",
        return_value=_gh_result(issues),
    ):
        await listener.tick_once(emit)

    assert emit.calls[0]["payload"]["labels"] == ["agent-task", "bug"]
