from __future__ import annotations

import pytest

from foundry.agents import AgentSettings, UnknownBackendError, make_agent
from foundry.agents.claude_cli import ClaudeCliAgent
from foundry.agents.codex_cli import CodexCliAgent
from foundry.agents.opencode_cli import OpencodeCliAgent
from foundry.agents.stub import StubAgent


def test_make_agent_returns_stub_backend() -> None:
    agent = make_agent(AgentSettings(backend="stub"))

    assert isinstance(agent, StubAgent)


def test_make_agent_returns_claude_cli_backend() -> None:
    agent = make_agent(AgentSettings(backend="claude_cli"))

    assert isinstance(agent, ClaudeCliAgent)


def test_make_agent_returns_codex_cli_backend() -> None:
    agent = make_agent(AgentSettings(backend="codex_cli"))

    assert isinstance(agent, CodexCliAgent)


def test_make_agent_returns_opencode_cli_backend() -> None:
    agent = make_agent(AgentSettings(backend="opencode_cli"))

    assert isinstance(agent, OpencodeCliAgent)


def test_make_agent_raises_on_unknown_backend() -> None:
    with pytest.raises(UnknownBackendError):
        make_agent(AgentSettings(backend="whatever"))
