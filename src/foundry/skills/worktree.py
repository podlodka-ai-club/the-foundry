"""Worktree skill — read-only wrapper around the orchestrator-pre-created worktree.

The orchestrator creates the worktree before launching the agent (so the env
subprocess sees a fixed FOUNDRY_WORKTREE / FOUNDRY_BRANCH). This skill is
idempotent: it just confirms the path exists and echoes the branch.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def open_worktree_impl() -> dict[str, Any]:
    raw = os.environ.get("FOUNDRY_WORKTREE")
    branch = os.environ.get("FOUNDRY_BRANCH", "")
    if not raw:
        return {"ok": False, "error": "worktree not initialized"}
    path = Path(raw)
    if not path.exists():
        return {"ok": False, "error": "worktree not initialized"}
    return {"ok": True, "worktree": str(path), "branch": branch}


__all__ = ["open_worktree_impl"]
