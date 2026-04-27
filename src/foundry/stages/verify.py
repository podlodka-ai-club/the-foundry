from __future__ import annotations

from pathlib import Path

from .. import shell
from ..config import Settings
from ..models import Task


def run(task: Task, worktree_path: Path, settings: Settings) -> dict:
    """STUB: runs `echo ok` in the worktree. Day 5 replaces with pytest/ruff/etc."""
    result = shell.run(["echo", "ok"], cwd=worktree_path)
    return {"passed": result.ok, "stdout": result.stdout.strip()}
