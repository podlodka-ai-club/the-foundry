from __future__ import annotations

from typing import Any, Callable

from .github import react_emoji_impl
from .pr import commit_and_push_pr_impl
from .run_lifecycle import mark_done_impl, mark_failed_impl
from .worktree import open_worktree_impl

SKILL_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "open_worktree": open_worktree_impl,
    "commit_and_push_pr": commit_and_push_pr_impl,
    "react_emoji": react_emoji_impl,
    "mark_done": mark_done_impl,
    "mark_failed": mark_failed_impl,
}

ALWAYS_AVAILABLE: tuple[str, ...] = ("call_subagent", "mark_milestone", "compact_context")

__all__ = ["SKILL_REGISTRY", "ALWAYS_AVAILABLE"]
