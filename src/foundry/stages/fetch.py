from __future__ import annotations

import json

from .. import shell, state
from ..config import Settings
from ..models import Task


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
        else:
            # re-queue only if still pending; don't clobber running/done/failed
            if existing.status.value == "pending":
                ready.append(existing)
    return ready
