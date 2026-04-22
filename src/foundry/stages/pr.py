from __future__ import annotations

from pathlib import Path

from .. import shell
from ..config import Settings
from ..models import Task


def run(task: Task, worktree_path: Path, branch_name: str, settings: Settings) -> dict:
    """Commit, push and open a PR against settings.target_repo.

    Idempotent-ish: if task already has a pr_url, callers should skip this stage.
    """
    shell.run(["git", "add", "-A"], cwd=worktree_path)

    status = shell.run(["git", "status", "--porcelain"], cwd=worktree_path)
    if not status.stdout.strip():
        raise RuntimeError("implement stage produced no changes — nothing to commit")

    commit_message = f"foundry: task #{task.issue_number} — {task.issue_title}"
    shell.run(["git", "commit", "-m", commit_message], cwd=worktree_path)
    shell.run(["git", "push", "-u", "origin", branch_name], cwd=worktree_path)

    body = (
        f"Automated PR from The Foundry (skeleton mode).\n\n"
        f"Closes #{task.issue_number}\n\n"
        f"Issue: {task.issue_title}"
    )
    pr_result = shell.run(
        [
            "gh", "pr", "create",
            "--repo", settings.target_repo,
            "--head", branch_name,
            "--base", "main",
            "--title", commit_message,
            "--body", body,
        ],
        cwd=worktree_path,
    )
    pr_url = pr_result.stdout.strip().splitlines()[-1]

    shell.run(
        [
            "gh", "issue", "close", str(task.issue_number),
            "--repo", task.repo,
            "--comment", f"Closed automatically by The Foundry after opening {pr_url}.",
        ],
        cwd=worktree_path,
    )

    return {"pr_url": pr_url, "branch": branch_name}
