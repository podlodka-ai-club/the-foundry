from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry.config import ConfigError, load_settings


def _base_env(tmp_path: Path) -> dict[str, str]:
    return {
        "SOURCE_REPO": "owner/sandbox",
        "TARGET_REPO": "owner/sandbox",
        "WORKTREE_ROOT": str(tmp_path / "wt"),
        "DB_PATH": str(tmp_path / "db.sqlite"),
        "ISSUE_LABEL": "agent-task",
        "POLL_INTERVAL_SECONDS": "30",
    }


def _empty_env(tmp_path: Path) -> Path:
    """Возвращает путь к гарантированно пустому .env, чтобы load_dotenv не подтянул реальный."""
    p = tmp_path / "empty.env"
    p.write_text("")
    return p


def test_load_settings_validates_coding_llm_value(tmp_path: Path) -> None:
    env = _base_env(tmp_path) | {"CODING_LLM": "GEMINI"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ConfigError, match="CODING_LLM"):
            load_settings(_empty_env(tmp_path))


def test_load_settings_requires_api_key_for_active_provider(tmp_path: Path) -> None:
    env = _base_env(tmp_path) | {"CODING_LLM": "DEEPSEEK"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ConfigError, match="DEEPSEEK_API_KEY"):
            load_settings(_empty_env(tmp_path))


def test_load_settings_supports_chatgpt_or_openai_api_key(tmp_path: Path) -> None:
    env = _base_env(tmp_path) | {"CODING_LLM": "CHATGPT", "CHATGPT_API_KEY": "sk-cg"}
    with patch.dict(os.environ, env, clear=True):
        settings = load_settings(_empty_env(tmp_path))
    assert settings.openai_api_key == "sk-cg"

    env = _base_env(tmp_path) | {"CODING_LLM": "CHATGPT", "OPENAI_API_KEY": "sk-oai"}
    with patch.dict(os.environ, env, clear=True):
        settings = load_settings(_empty_env(tmp_path))
    assert settings.openai_api_key == "sk-oai"


def test_load_settings_reads_optional_model_names(tmp_path: Path) -> None:
    env = _base_env(tmp_path) | {
        "CODING_LLM": "ANTHROPIC",
        "ANTHROPIC_API_KEY": "sk-a",
        "ANTHROPIC_MODEL_NAME": "claude-custom",
        "AIDER_TIMEOUT_SECONDS": "120",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = load_settings(_empty_env(tmp_path))

    assert settings.anthropic_model_name == "claude-custom"
    assert settings.aider_timeout_seconds == 120
    assert settings.coding_llm == "ANTHROPIC"


def test_load_settings_requires_repos(tmp_path: Path) -> None:
    env = _base_env(tmp_path) | {"CODING_LLM": "DEEPSEEK", "DEEPSEEK_API_KEY": "x"}
    env.pop("SOURCE_REPO")
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ConfigError, match="SOURCE_REPO"):
            load_settings(_empty_env(tmp_path))
