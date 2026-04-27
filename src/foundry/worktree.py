from __future__ import annotations

from pathlib import Path

from . import shell

BASE_DIR_NAME = "_base"


def base_repo_path(worktree_root: Path) -> Path:
    return worktree_root / BASE_DIR_NAME


def ensure_base_repo(worktree_root: Path, source_repo: str) -> Path:
    """Clone source_repo into worktree_root/_base if not present, then fetch."""
    worktree_root.mkdir(parents=True, exist_ok=True)
    base = base_repo_path(worktree_root)
    if not base.exists():
        shell.run(["gh", "repo", "clone", source_repo, str(base), "--", "--no-checkout"])
        shell.run(["git", "fetch", "origin"], cwd=base)
        shell.run(["git", "checkout", "main"], cwd=base)
    else:
        shell.run(["git", "fetch", "origin"], cwd=base)
        shell.run(["git", "checkout", "main"], cwd=base)
        shell.run(["git", "reset", "--hard", "origin/main"], cwd=base)
    return base


def create_worktree(
    worktree_root: Path,
    task_id: int,
    base_branch: str = "main",
) -> tuple[Path, str]:
    base = base_repo_path(worktree_root)
    if not base.exists():
        raise RuntimeError(
            f"base repo not found at {base} — call ensure_base_repo first"
        )

    worktree_path = (worktree_root / f"task-{task_id}").resolve()
    branch_name = f"foundry/task-{task_id}"

    if worktree_path.exists():
        cleanup_worktree(base, worktree_path)

    shell.run(
        ["git", "worktree", "add", str(worktree_path), "-b", branch_name, base_branch],
        cwd=base,
    )
    return worktree_path, branch_name


def cleanup_worktree(base_repo: Path, worktree_path: Path) -> None:
    shell.run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        cwd=base_repo,
        check=False,
    )
