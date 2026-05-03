from __future__ import annotations

import pytest

from foundry.agents import AgentSettings, AgentStage, UnknownBackendError, make_agent
from foundry.agents.claude_cli import ClaudeCliAgent
from foundry.agents.codex_cli import CodexCliAgent
from foundry.agents.opencode_cli import OpencodeCliAgent
from foundry.agents.stub import StubAgent


def test_make_agent_returns_stub_backend() -> None:
    settings = AgentSettings(stage=AgentStage.PLAN, backend="stub")

    agent = make_agent(settings)

    assert isinstance(agent, StubAgent)
    assert agent.stage is AgentStage.PLAN


def test_make_agent_returns_claude_cli_backend() -> None:
    settings = AgentSettings(stage=AgentStage.IMPLEMENT, backend="claude_cli")

    agent = make_agent(settings)

    assert isinstance(agent, ClaudeCliAgent)
    assert agent.stage is AgentStage.IMPLEMENT


def test_make_agent_returns_codex_cli_backend() -> None:
    settings = AgentSettings(stage=AgentStage.PLAN, backend="codex_cli")

    agent = make_agent(settings)

    assert isinstance(agent, CodexCliAgent)
    assert agent.stage is AgentStage.PLAN


def test_make_agent_returns_opencode_cli_backend() -> None:
    settings = AgentSettings(stage=AgentStage.VERIFY, backend="opencode_cli")

    agent = make_agent(settings)

    assert isinstance(agent, OpencodeCliAgent)
    assert agent.stage is AgentStage.VERIFY


def test_make_agent_raises_on_unknown_backend() -> None:
    settings = AgentSettings(stage=AgentStage.PLAN, backend="whatever")

    with pytest.raises(UnknownBackendError):
        make_agent(settings)
