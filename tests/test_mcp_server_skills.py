"""Surface tests for the MCP server's tool set.

Post-trim shape:
- ``SKILL_REGISTRY``: ``commit_and_push_pr``, ``telegram_reply``, ``wait_for_human``.
- Hardcoded MCP tool: ``call_subagent``.

All control-plane tools (``mark_done`` / ``mark_failed`` / ``mark_milestone``)
were dropped in favour of a ``STATUS:`` marker parsed from the agent's
final reply (see :mod:`foundry.status_marker`). Domain helpers
(``run_tests``, ``react_emoji``, ``open_worktree``, ``open_pr_worktree``)
were dropped in favour of the agent calling ``Bash`` / ``gh`` directly.
"""

from __future__ import annotations

import asyncio
import importlib

import pytest


def _reload_server():
    import foundry.mcp.server as server_mod

    return importlib.reload(server_mod)


def test_skill_registry_is_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_ENABLED_SKILLS", raising=False)

    server = _reload_server()

    expected = {"commit_and_push_pr", "telegram_reply", "wait_for_human"}
    assert expected == server._REGISTERED


def test_dropped_skills_are_not_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_ENABLED_SKILLS", raising=False)

    server = _reload_server()

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
    assert dropped.isdisjoint(server._REGISTERED)


def test_call_subagent_tool_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """`call_subagent` is wired via @mcp.tool() decorator at import time
    (not via SKILL_REGISTRY) — verify it's still exposed to the agent."""
    monkeypatch.delenv("FOUNDRY_ENABLED_SKILLS", raising=False)

    server = _reload_server()
    tools = asyncio.run(server.mcp.list_tools())
    names = {getattr(t, "name", None) for t in tools}

    assert "call_subagent" in names
