from __future__ import annotations

import importlib

import pytest


def _reload_server():
    import foundry.mcp.server as server_mod

    return importlib.reload(server_mod)


def test_skill_registered_when_in_enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_ENABLED_SKILLS", "mark_done,mark_failed")

    server = _reload_server()

    assert "mark_done" in server._REGISTERED
    assert "mark_failed" in server._REGISTERED


def test_skill_not_registered_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_ENABLED_SKILLS", "mark_done")

    server = _reload_server()

    assert "mark_done" in server._REGISTERED
    assert "open_worktree" not in server._REGISTERED
    assert "commit_and_push_pr" not in server._REGISTERED


def test_always_available_tools_present_regardless_of_skills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`mark_milestone`, `call_subagent`, `compact_context` register via @mcp.tool()
    decorators at import-time regardless of FOUNDRY_ENABLED_SKILLS."""
    monkeypatch.delenv("FOUNDRY_ENABLED_SKILLS", raising=False)

    server = _reload_server()

    import asyncio

    tools = asyncio.run(server.mcp.list_tools())
    names = {getattr(t, "name", None) for t in tools}
    assert {"mark_milestone", "call_subagent", "compact_context"}.issubset(names)
