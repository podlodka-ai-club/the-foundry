"""Sanity checks for the trimmed MCP server.

Control-plane tools (mark_done / mark_failed / mark_milestone) and the
``compact_context`` stub were removed. Domain helpers (run_tests,
react_emoji, open_worktree, open_pr_worktree) were dropped along with
their skill files. The server now surfaces only :data:`SKILL_REGISTRY` +
``call_subagent``.
"""

from __future__ import annotations

from foundry.mcp import server as mcp_server


def test_registered_set_equals_skill_registry() -> None:
    """``_REGISTERED`` only tracks dynamic registrations from
    :data:`SKILL_REGISTRY`. ``call_subagent`` lives outside that set
    (it's bound directly via ``@mcp.tool()`` at import time)."""
    from foundry.skills import SKILL_REGISTRY

    assert set(SKILL_REGISTRY) == mcp_server._REGISTERED


def test_registered_does_not_include_dropped_tools() -> None:
    """No mark_done/mark_failed/mark_milestone/compact_context anymore."""
    dropped = {
        "mark_done",
        "mark_failed",
        "mark_milestone",
        "compact_context",
        "open_worktree",
        "open_pr_worktree",
        "react_emoji",
        "run_tests",
    }
    assert dropped.isdisjoint(mcp_server._REGISTERED)
