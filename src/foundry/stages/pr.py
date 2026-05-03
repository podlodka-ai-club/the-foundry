from __future__ import annotations

from pathlib import Path

from langfuse import observe

from .. import shell
from ..config import Settings
from ..models import Task


@observe(name="stage.pr")
def run(
    task: Task,
    worktree_path: Path,
    branch_name: str,
    settings: Settings,
    report: str | None = None,
) -> dict:
    """Commit, push and open a PR against settings.target_repo.

    Idempotent-ish: if task already has a pr_url, callers should skip this stage.
    `report` is an optional human-readable summary (from verify, or the
    implement agent response until a real verifier exists) embedded in the PR
    body.
    """
    commit_message = f"foundry: task #{task.issue_number} — {task.issue_title}"
    commit_result = commit_and_push_changes(
        task, worktree_path, branch_name, commit_message
    )

    body_parts = [
        "Automated PR from The Foundry (skeleton mode).",
        "",
        f"Closes #{task.issue_number}",
        "",
        f"Issue: {task.issue_title}",
    ]
    if report:
        body_parts += ["", "## Отчёт", "", report.strip()]
    body = "\n".join(body_parts)
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

    return {
        "pr_url": pr_url,
        "branch": branch_name,
        "touched_files": commit_result["touched_files"],
        "files_changed": commit_result["files_changed"],
    }


MAX_FILES_PER_PR = 40
FORBIDDEN_PATH_SUBSTRINGS = ("__pycache__", ".pyc", ".DS_Store", ".venv/")


def commit_and_push_changes(
    task: Task,
    worktree_path: Path,
    branch_name: str,
    commit_message: str,
) -> dict:
    """Commit current worktree changes and push them to the PR branch."""
    shell.run(["git", "add", "-A"], cwd=worktree_path)

    status = shell.run(["git", "status", "--porcelain"], cwd=worktree_path)
    changes = [line for line in status.stdout.splitlines() if line.strip()]
    if not changes:
        raise RuntimeError("implement stage produced no changes — nothing to commit")
    _sanity_check_changes(changes)
    touched_files = [_porcelain_path(line) for line in changes]

    shell.run(["git", "commit", "-m", commit_message], cwd=worktree_path)
    shell.run(["git", "push", "-u", "origin", branch_name], cwd=worktree_path)
    return {
        "branch": branch_name,
        "files_changed": len(changes),
        "touched_files": touched_files,
    }


def _sanity_check_changes(porcelain_lines: list[str]) -> None:
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
        path = _porcelain_path(line)
        if any(sub in path for sub in FORBIDDEN_PATH_SUBSTRINGS):
            bad.append(path)
    if bad:
        raise RuntimeError(
            f"refusing to commit: forbidden paths in agent changes: {bad[:5]}"
        )


def _porcelain_path(line: str) -> str:
    path = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in path:
        return path.split(" -> ", 1)[1].strip()
    return path
