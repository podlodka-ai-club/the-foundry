from __future__ import annotations

import json

from .. import shell, state
from ..config import Settings
from ..models import Stage, Task, TaskStatus


PRIORITY_RANK = {
    "priority/p0": 0,
    "priority/p1": 1,
}


def _issue_labels(settings: Settings) -> tuple[str, ...]:
    return settings.issue_labels or (
        (settings.issue_label,) if settings.issue_label else ()
    )


def _issue_list_cmd(settings: Settings) -> list[str]:
    cmd = [
        "gh", "issue", "list",
        "--repo", settings.source_repo,
        "--state", "open",
        "--json", "number,title,body,labels",
        "--limit", str(settings.issue_limit),
    ]
    for label in _issue_labels(settings):
        cmd.extend(["--label", label])
    if settings.issue_assignee:
        cmd.extend(["--assignee", settings.issue_assignee])
    if settings.issue_milestone:
        cmd.extend(["--milestone", settings.issue_milestone])
    return cmd


def _issue_priority(issue: dict) -> int:
    labels = issue.get("labels") or []
    names = {
        label.get("name", "").lower()
        for label in labels
        if isinstance(label, dict)
    }
    return min(
        (PRIORITY_RANK[name] for name in names if name in PRIORITY_RANK),
        default=99,
    )


def _issue_to_task(settings: Settings, issue: dict) -> Task:
    return Task(
        repo=settings.source_repo,
        issue_number=issue["number"],
        issue_title=issue["title"],
        issue_body=issue.get("body") or "",
    )


def _upsert_issue(settings: Settings, issue: dict) -> Task:
    task = _issue_to_task(settings, issue)
    return state.upsert_task(settings.db_path, task)


def fetch_issue(settings: Settings, issue_number: int) -> Task:
    """Upsert a single issue for a manual run, bypassing label queue filters."""
    result = shell.run(
        [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--repo", settings.source_repo,
            "--json", "number,title,body",
        ]
    )
    issue = json.loads(result.stdout or "{}")
    return _upsert_issue(settings, issue)


def fetch(settings: Settings) -> list[Task]:
    """Pull open issues with the configured label and upsert into the DB.

    Returns the list of tasks that are ready to be processed (pending status).
    """
    result = shell.run(_issue_list_cmd(settings))
    issues = json.loads(result.stdout or "[]")
    issues = sorted(issues, key=_issue_priority)

    ready: list[Task] = []
    ready_ids: set[int] = set()
    for issue in issues:
        existing = state.get_task_by_issue(
            settings.db_path, settings.source_repo, issue["number"]
        )
        if existing is None:
            task = _upsert_issue(settings, issue)
            ready.append(task)
            if task.id is not None:
                ready_ids.add(task.id)
        else:
            # Re-queue pending tasks and resume interrupted running tasks.
            if existing.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
                ready.append(existing)
                if existing.id is not None:
                    ready_ids.add(existing.id)
    for task in state.list_tasks(settings.db_path, TaskStatus.PENDING):
        if task.repo != settings.source_repo or task.id in ready_ids:
            continue
        ready.append(task)
        if task.id is not None:
            ready_ids.add(task.id)
    for task in state.list_tasks(settings.db_path, TaskStatus.RUNNING):
        if task.repo != settings.source_repo or task.id in ready_ids:
            continue
        if task.current_stage in {
            Stage.IMPLEMENT,
            Stage.VERIFY,
            Stage.PR,
            Stage.CONTEXT,
            Stage.PLAN,
            Stage.FETCH,
        }:
            ready.append(task)
    return ready
