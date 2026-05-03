from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from foundry import state
from foundry.config import Settings
from foundry.models import Task
from foundry.shell import Result
from foundry.stages import fetch as fetch_stage


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        source_repo="owner/sandbox",
        target_repo="owner/sandbox",
        issue_label="agent-task",
        worktree_root=tmp_path / "worktrees",
        db_path=tmp_path / "foundry.sqlite",
        poll_interval_seconds=30,
        issue_assignee="octocat",
        issue_milestone="v1",
        issue_labels=("agent-task", "queue/backend"),
        issue_limit=25,
    )


def test_fetch_filters_and_sorts_by_priority_labels(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    issues = [
        {
            "number": 3,
            "title": "normal",
            "body": "",
            "labels": [{"name": "agent-task"}],
        },
        {
            "number": 1,
            "title": "p1",
            "body": "",
            "labels": [{"name": "priority/p1"}],
        },
        {
            "number": 2,
            "title": "p0",
            "body": "",
            "labels": [{"name": "priority/p0"}],
        },
    ]
    seen_cmd: list[str] = []

    def _run(cmd: list[str]) -> Result:
        seen_cmd.extend(cmd)
        return Result(returncode=0, stdout=json.dumps(issues), stderr="")

    with patch("foundry.stages.fetch.shell.run", side_effect=_run):
        tasks = fetch_stage.fetch(settings)

    assert [task.issue_number for task in tasks] == [2, 1, 3]
    assert seen_cmd == [
        "gh",
        "issue",
        "list",
        "--repo", "owner/sandbox",
        "--state", "open",
        "--json", "number,title,body,labels",
        "--limit", "25",
        "--label", "agent-task",
        "--label", "queue/backend",
        "--assignee", "octocat",
        "--milestone", "v1",
    ]


def test_fetch_issue_bypasses_queue_filters(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    seen_cmd: list[str] = []

    def _run(cmd: list[str]) -> Result:
        seen_cmd.extend(cmd)
        return Result(
            returncode=0,
            stdout=json.dumps({"number": 7, "title": "manual", "body": "go"}),
            stderr="",
        )

    with patch("foundry.stages.fetch.shell.run", side_effect=_run):
        task = fetch_stage.fetch_issue(settings, 7)

    assert task.issue_number == 7
    assert task.issue_title == "manual"
    assert seen_cmd == [
        "gh",
        "issue",
        "view",
        "7",
        "--repo", "owner/sandbox",
        "--json", "number,title,body",
    ]


def test_fetch_includes_pending_tasks_from_sqlite_queue(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    state.init_db(settings.db_path)
    queued = state.upsert_task(
        settings.db_path,
        Task(
            repo=settings.source_repo,
            issue_number=99,
            issue_title="already queued",
            issue_body="",
        ),
    )

    with patch(
        "foundry.stages.fetch.shell.run",
        return_value=Result(returncode=0, stdout="[]", stderr=""),
    ):
        tasks = fetch_stage.fetch(settings)

    assert [task.id for task in tasks] == [queued.id]
