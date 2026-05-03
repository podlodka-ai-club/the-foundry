from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    source_repo: str
    target_repo: str
    issue_label: str
    worktree_root: Path
    db_path: Path
    poll_interval_seconds: int
    github_token: str | None = None
    max_implement_attempts: int = 2
    verify_commands: tuple[tuple[str, ...], ...] | None = None
    verify_command_timeout_sec: int = 300
    verify_diff_max_bytes: int = 200_000


def _parse_verify_commands(raw: str) -> tuple[tuple[str, ...], ...] | None:
    """Parse VERIFY_COMMANDS env var as JSON list-of-list-of-strings.

    Empty/missing → None (caller falls back to auto-detect).
    Malformed JSON or wrong shape → ConfigError so startup fails fast.
    """
    raw = raw.strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"VERIFY_COMMANDS is not valid JSON: {e}") from e
    if not isinstance(parsed, list):
        raise ConfigError("VERIFY_COMMANDS must be a JSON array of argv arrays")
    out: list[tuple[str, ...]] = []
    for item in parsed:
        if not isinstance(item, list) or not all(isinstance(x, str) for x in item):
            raise ConfigError(
                "VERIFY_COMMANDS entries must be arrays of strings, e.g. "
                '[["ruff","check","."],["pytest","-x"]]'
            )
        if not item:
            raise ConfigError("VERIFY_COMMANDS entries must be non-empty argv arrays")
        out.append(tuple(item))
    return tuple(out)


def load_settings(env_path: Path | None = None) -> Settings:
    if env_path is None:
        load_dotenv()
    else:
        load_dotenv(env_path)

    source_repo = os.environ.get("SOURCE_REPO", "").strip()
    target_repo = os.environ.get("TARGET_REPO", "").strip()
    if not source_repo or not target_repo:
        raise ConfigError("SOURCE_REPO and TARGET_REPO must be set (owner/name)")

    token = os.environ.get("GITHUB_TOKEN", "").strip() or None

    return Settings(
        source_repo=source_repo,
        target_repo=target_repo,
        issue_label=os.environ.get("ISSUE_LABEL", "agent-task").strip(),
        worktree_root=Path(os.environ.get("WORKTREE_ROOT", "./worktrees")).resolve(),
        db_path=Path(os.environ.get("DB_PATH", "./data/foundry.sqlite")).resolve(),
        poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "30")),
        github_token=token,
        max_implement_attempts=int(os.environ.get("MAX_IMPLEMENT_ATTEMPTS", "2")),
        verify_commands=_parse_verify_commands(os.environ.get("VERIFY_COMMANDS", "")),
        verify_command_timeout_sec=int(
            os.environ.get("VERIFY_COMMAND_TIMEOUT_SEC", "300")
        ),
        verify_diff_max_bytes=int(os.environ.get("VERIFY_DIFF_MAX_BYTES", "200000")),
    )
