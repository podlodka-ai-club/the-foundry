"""commit_and_push_pr skill — same logic as stages/pr.py:run, but Task-free.

Reads worktree / branch / repos / issue number from environment variables set
by the orchestrator; returns a structured result instead of raising.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from foundry import shell
from foundry.stages.pr import sanity_check_changes


def commit_and_push_pr_impl(*, title: str, body: str = "") -> dict[str, Any]:
    worktree_raw = os.environ.get("FOUNDRY_WORKTREE")
    branch = os.environ.get("FOUNDRY_BRANCH")
    target_repo = os.environ.get("FOUNDRY_TARGET_REPO")
    source_repo = os.environ.get("FOUNDRY_SOURCE_REPO")
    issue_number = os.environ.get("FOUNDRY_ISSUE_NUMBER")

    if not worktree_raw or not branch or not target_repo:
        return {"ok": False, "error": "worktree/branch/target_repo missing"}

    worktree = Path(worktree_raw)

    shell.run(["git", "add", "-A"], cwd=worktree)
    status = shell.run(["git", "status", "--porcelain"], cwd=worktree)
    changes = [line for line in status.stdout.splitlines() if line.strip()]
    if not changes:
        return {"ok": False, "reason": "no_changes"}

    try:
        sanity_check_changes(changes)
    except RuntimeError as exc:
        return {"ok": False, "reason": "sanity_failed", "error": str(exc)}

    commit_args = ["git", "commit", "-m", title]
    if body:
        commit_args += ["-m", body]
    shell.run(commit_args, cwd=worktree)
    shell.run(["git", "push", "--set-upstream", "origin", branch], cwd=worktree)

    pr_result = shell.run(
        [
            "gh", "pr", "create",
            "--repo", target_repo,
            "--base", "main",
            "--head", branch,
            "--title", title,
            "--body", body,
        ],
        cwd=worktree,
    )
    pr_url = pr_result.stdout.strip().splitlines()[-1]

    if issue_number and source_repo:
        shell.run(
            [
                "gh", "issue", "close", str(issue_number),
                "--repo", source_repo,
                "--comment", f"Closed automatically by The Foundry after opening {pr_url}.",
            ],
            cwd=worktree,
            check=False,
        )

    return {"ok": True, "pr_url": pr_url}


__all__ = ["commit_and_push_pr_impl"]
