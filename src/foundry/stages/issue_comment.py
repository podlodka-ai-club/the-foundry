from __future__ import annotations

from pathlib import Path

from langfuse import observe

from .. import shell
from ..config import Settings
from ..models import Task


@observe(name="stage.issue_comment")
def run(
    task: Task,
    settings: Settings,
    body: str,
    *,
    cwd: Path | None = None,
) -> dict:
    """Ask for human input by commenting on the source GitHub issue."""
    comment = body.strip()
    if not comment:
        comment = "The agent needs human input before it can continue."

    shell.run(
        [
            "gh",
            "issue",
            "comment",
            str(task.issue_number),
            "--repo",
            task.repo,
            "--body",
            comment,
        ],
        cwd=cwd,
    )
    return {"issue_number": task.issue_number, "comment": comment}
