from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


SUPPORTED_CODING_LLMS = ("DEEPSEEK", "ANTHROPIC", "CHATGPT")


@dataclass(frozen=True)
class Settings:
    source_repo: str
    target_repo: str
    issue_label: str
    worktree_root: Path
    db_path: Path
    poll_interval_seconds: int
    coding_llm: str = "DEEPSEEK"
    deepseek_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    deepseek_model_name: str | None = None
    anthropic_model_name: str | None = None
    chatgpt_model_name: str | None = None
    aider_timeout_seconds: int = 600
    github_token: str | None = None


def _env_or_none(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def load_settings(env_path: Path | None = None) -> Settings:
    if env_path is None:
        load_dotenv()
    else:
        load_dotenv(env_path)

    source_repo = os.environ.get("SOURCE_REPO", "").strip()
    target_repo = os.environ.get("TARGET_REPO", "").strip()
    if not source_repo or not target_repo:
        raise ConfigError("SOURCE_REPO and TARGET_REPO must be set (owner/name)")

    coding_llm = os.environ.get("CODING_LLM", "DEEPSEEK").strip().upper()
    if coding_llm not in SUPPORTED_CODING_LLMS:
        raise ConfigError(
            f"CODING_LLM must be one of {', '.join(SUPPORTED_CODING_LLMS)}, got {coding_llm!r}"
        )

    deepseek_key = _env_or_none("DEEPSEEK_API_KEY")
    anthropic_key = _env_or_none("ANTHROPIC_API_KEY")
    # OpenAI ключ принимаем под обоими привычными именами; OPENAI_API_KEY — стандарт.
    openai_key = _env_or_none("OPENAI_API_KEY") or _env_or_none("CHATGPT_API_KEY")

    required_key = {
        "DEEPSEEK": deepseek_key,
        "ANTHROPIC": anthropic_key,
        "CHATGPT": openai_key,
    }[coding_llm]
    if required_key is None:
        env_hint = {
            "DEEPSEEK": "DEEPSEEK_API_KEY",
            "ANTHROPIC": "ANTHROPIC_API_KEY",
            "CHATGPT": "OPENAI_API_KEY (or CHATGPT_API_KEY)",
        }[coding_llm]
        raise ConfigError(f"{env_hint} is required for CODING_LLM={coding_llm}")

    return Settings(
        source_repo=source_repo,
        target_repo=target_repo,
        issue_label=os.environ.get("ISSUE_LABEL", "agent-task").strip(),
        worktree_root=Path(os.environ.get("WORKTREE_ROOT", "./worktrees")).resolve(),
        db_path=Path(os.environ.get("DB_PATH", "./data/foundry.sqlite")).resolve(),
        poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "30")),
        coding_llm=coding_llm,
        deepseek_api_key=deepseek_key,
        anthropic_api_key=anthropic_key,
        openai_api_key=openai_key,
        deepseek_model_name=_env_or_none("DEEPSEEK_MODEL_NAME"),
        anthropic_model_name=_env_or_none("ANTHROPIC_MODEL_NAME"),
        chatgpt_model_name=_env_or_none("CHATGPT_MODEL_NAME"),
        aider_timeout_seconds=int(os.environ.get("AIDER_TIMEOUT_SECONDS", "600")),
        github_token=_env_or_none("GITHUB_TOKEN"),
    )
