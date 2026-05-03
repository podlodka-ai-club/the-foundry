from __future__ import annotations

import os

import pytest

from foundry.agents import AgentSettings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Prevent .env in the repo root from leaking into tests.
    monkeypatch.setattr("foundry.agents.config.load_dotenv", lambda *a, **kw: False)
    for key in list(os.environ):
        if key.startswith("AGENT_") or key == "CODING_AGENT":
            monkeypatch.delenv(key, raising=False)


def test_from_env_returns_defaults_when_nothing_set() -> None:
    settings = AgentSettings.from_env()

    assert settings.backend == "stub"
    assert settings.model == "haiku"
    assert settings.max_turns == 50
    assert settings.timeout_sec == 600
    assert settings.mcp_config is None


def test_from_env_reads_coding_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_AGENT", "claude_cli")

    assert AgentSettings.from_env().backend == "claude_cli"


def test_from_env_reads_agent_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_MODEL", "sonnet")

    assert AgentSettings.from_env().model == "sonnet"


def test_from_env_parses_integer_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_MAX_TURNS", "7")
    monkeypatch.setenv("AGENT_TIMEOUT_SEC", "42")

    settings = AgentSettings.from_env()

    assert settings.max_turns == 7
    assert settings.timeout_sec == 42


def test_from_env_reads_mcp_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_MCP_CONFIG", "/tmp/foo.json")

    settings = AgentSettings.from_env()

    assert settings.mcp_config is not None
    assert str(settings.mcp_config) == "/tmp/foo.json"
