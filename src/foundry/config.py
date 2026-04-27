from __future__ import annotations

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
    )
