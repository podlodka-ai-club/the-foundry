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
    # Listeners enabled by id. Empty tuple = all listeners (default).
    listeners_enabled: tuple[str, ...] = ()
    github_poll_sec: int = 30
    # Telegram listener config. Listener is silently skipped if token absent
    # OR allowlist empty — both are required for any traffic to be admitted.
    telegram_bot_token: str | None = None
    telegram_allowed_chat_ids: tuple[int, ...] = ()
    telegram_poll_sec: int = 25
    # GithubPrReviewListener — polls `gh search prs` for PRs awaiting the user's
    # attention. Silently skipped if `github_user` is not set.
    github_user: str | None = None
    github_pr_review_poll_sec: int = 60
    github_pr_review_max_age_days: int = 30
    github_pr_review_skip_repos: tuple[str, ...] = ()
    github_pr_review_include_authored: bool = True
    # Umbrella folder containing local checkouts for repos covered by the
    # ``pr_review`` automation. Required to dispatch pr_review runs; if
    # unset, runs fail with ``failure_kind=infra``.
    pr_review_base_path: Path | None = None


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

    listeners_raw = os.environ.get("LISTENERS_ENABLED", "").strip()
    listeners_enabled: tuple[str, ...] = (
        tuple(s.strip() for s in listeners_raw.split(",") if s.strip())
        if listeners_raw
        else ()
    )

    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or None
    tg_allowed_raw = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    tg_allowed: tuple[int, ...] = (
        tuple(int(s.strip()) for s in tg_allowed_raw.split(",") if s.strip())
        if tg_allowed_raw
        else ()
    )

    gh_user = os.environ.get("GITHUB_USER", "").strip() or None
    gh_skip_raw = os.environ.get("GITHUB_PR_REVIEW_SKIP_REPOS", "").strip()
    gh_skip: tuple[str, ...] = (
        tuple(s.strip() for s in gh_skip_raw.split(",") if s.strip())
        if gh_skip_raw
        else ()
    )
    gh_include_authored = (
        os.environ.get("GITHUB_PR_REVIEW_INCLUDE_AUTHORED", "true").strip().lower()
        not in ("0", "false", "no")
    )
    pr_review_base_raw = os.environ.get("PR_REVIEW_BASE_PATH", "").strip()
    pr_review_base = (
        Path(pr_review_base_raw).expanduser().resolve()
        if pr_review_base_raw
        else None
    )

    return Settings(
        source_repo=source_repo,
        target_repo=target_repo,
        issue_label=os.environ.get("ISSUE_LABEL", "agent-task").strip(),
        worktree_root=Path(os.environ.get("WORKTREE_ROOT", "./worktrees")).resolve(),
        db_path=Path(os.environ.get("DB_PATH", "./data/foundry.sqlite")).resolve(),
        poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "30")),
        github_token=token,
        listeners_enabled=listeners_enabled,
        github_poll_sec=int(os.environ.get("GITHUB_POLL_SEC", "30")),
        telegram_bot_token=tg_token,
        telegram_allowed_chat_ids=tg_allowed,
        telegram_poll_sec=int(os.environ.get("TELEGRAM_POLL_SEC", "25")),
        github_user=gh_user,
        github_pr_review_poll_sec=int(
            os.environ.get("GITHUB_PR_REVIEW_POLL_SEC", "60")
        ),
        github_pr_review_max_age_days=int(
            os.environ.get("GITHUB_PR_REVIEW_MAX_AGE_DAYS", "30")
        ),
        github_pr_review_skip_repos=gh_skip,
        github_pr_review_include_authored=gh_include_authored,
        pr_review_base_path=pr_review_base,
    )
