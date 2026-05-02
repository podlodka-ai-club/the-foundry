from __future__ import annotations

import os

import pytest

from foundry.agents import AgentSettings, AgentStage


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Prevent .env in the repo root from leaking into tests.
    monkeypatch.setattr("foundry.agents.config.load_dotenv", lambda *a, **kw: False)
    for key in list(os.environ):
        if key.startswith("AGENT_") or key == "CODING_AGENT":
            monkeypatch.delenv(key, raising=False)


def test_from_env_returns_defaults_when_nothing_set() -> None:
    settings = AgentSettings.from_env(AgentStage.PLAN)

    assert settings.stage is AgentStage.PLAN
    assert settings.backend == "stub"
    assert settings.model == "haiku"
    assert settings.max_turns == 50
    assert settings.timeout_sec == 600


def test_from_env_global_coding_agent_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_AGENT", "claude_cli")

    settings = AgentSettings.from_env(AgentStage.IMPLEMENT)

    assert settings.backend == "claude_cli"


def test_from_env_per_stage_backend_beats_global(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_AGENT", "stub")
    monkeypatch.setenv("AGENT_IMPLEMENT_BACKEND", "claude_cli")

    implement = AgentSettings.from_env(AgentStage.IMPLEMENT)
    plan = AgentSettings.from_env(AgentStage.PLAN)

    assert implement.backend == "claude_cli"
    assert plan.backend == "stub"


def test_from_env_per_stage_model_beats_global(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_MODEL", "sonnet")
    monkeypatch.setenv("AGENT_VERIFY_MODEL", "opus")

    verify = AgentSettings.from_env(AgentStage.VERIFY)
    plan = AgentSettings.from_env(AgentStage.PLAN)

    assert verify.model == "opus"
    assert plan.model == "sonnet"


def test_from_env_parses_integer_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_PLAN_MAX_TURNS", "7")
    monkeypatch.setenv("AGENT_PLAN_TIMEOUT_SEC", "42")

    settings = AgentSettings.from_env(AgentStage.PLAN)

    assert settings.max_turns == 7
    assert settings.timeout_sec == 42


def test_from_env_default_max_turns_per_stage_differs() -> None:
    verify = AgentSettings.from_env(AgentStage.VERIFY)
    implement = AgentSettings.from_env(AgentStage.IMPLEMENT)

    assert verify.max_turns == 20
    assert implement.max_turns == 50


def test_from_env_mcp_config_default_is_none() -> None:
    settings = AgentSettings.from_env(AgentStage.IMPLEMENT)

    assert settings.mcp_config is None


def test_from_env_mcp_config_global(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_MCP_CONFIG", "/tmp/foo.json")

    settings = AgentSettings.from_env(AgentStage.IMPLEMENT)

    assert settings.mcp_config is not None
    assert str(settings.mcp_config) == "/tmp/foo.json"


def test_from_env_mcp_config_per_stage_beats_global(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_MCP_CONFIG", "/tmp/global.json")
    monkeypatch.setenv("AGENT_IMPLEMENT_MCP_CONFIG", "/tmp/impl.json")

    impl = AgentSettings.from_env(AgentStage.IMPLEMENT)
    plan = AgentSettings.from_env(AgentStage.PLAN)

    assert str(impl.mcp_config) == "/tmp/impl.json"
    assert str(plan.mcp_config) == "/tmp/global.json"
