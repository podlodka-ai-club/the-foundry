from __future__ import annotations

import json

from .. import shell, state
from ..config import Settings
from ..models import Stage, Task, TaskStatus


def fetch(settings: Settings) -> list[Task]:
    """Pull open issues with the configured label and upsert into the DB.

    Returns the list of tasks that are ready to be processed (pending status).
    """
    result = shell.run(
        [
            "gh", "issue", "list",
            "--repo", settings.source_repo,
            "--label", settings.issue_label,
            "--state", "open",
            "--json", "number,title,body",
            "--limit", "50",
        ]
    )
    issues = json.loads(result.stdout or "[]")

    ready: list[Task] = []
    ready_ids: set[int] = set()
    for issue in issues:
        existing = state.get_task_by_issue(
            settings.db_path, settings.source_repo, issue["number"]
        )
        if existing is None:
            task = Task(
                repo=settings.source_repo,
                issue_number=issue["number"],
                issue_title=issue["title"],
                issue_body=issue.get("body") or "",
            )
            task = state.upsert_task(settings.db_path, task)
            ready.append(task)
            if task.id is not None:
                ready_ids.add(task.id)
        else:
            # Re-queue pending tasks and resume interrupted running tasks.
            if existing.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
                ready.append(existing)
                if existing.id is not None:
                    ready_ids.add(existing.id)
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
