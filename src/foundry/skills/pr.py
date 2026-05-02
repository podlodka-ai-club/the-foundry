"""commit_and_push_pr skill — Task-free PR creation logic.

Reads worktree / branch / repos / issue number from environment variables set
by the orchestrator; returns a structured result instead of raising.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from foundry import shell

MAX_FILES_PER_PR = 40
FORBIDDEN_PATH_SUBSTRINGS = ("__pycache__", ".pyc", ".DS_Store", ".venv/")


def sanity_check_changes(porcelain_lines: list[str]) -> None:
    """Reject suspicious worktree state before committing.

    Guards against agents accidentally copying parent-repo artifacts into the
    sandbox: build caches, dotfiles, or very large file sets.
    """
    if len(porcelain_lines) > MAX_FILES_PER_PR:
        raise RuntimeError(
            f"refusing to commit: agent produced {len(porcelain_lines)} changed "
            f"files (limit {MAX_FILES_PER_PR}) — likely a sandbox escape"
        )
    bad: list[str] = []
    for line in porcelain_lines:
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if any(sub in path for sub in FORBIDDEN_PATH_SUBSTRINGS):
            bad.append(path)
    if bad:
        raise RuntimeError(
            f"refusing to commit: forbidden paths in agent changes: {bad[:5]}"
        )


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


__all__ = [
    "commit_and_push_pr_impl",
    "sanity_check_changes",
    "MAX_FILES_PER_PR",
    "FORBIDDEN_PATH_SUBSTRINGS",
]
