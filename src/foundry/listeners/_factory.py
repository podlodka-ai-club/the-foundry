from __future__ import annotations

import structlog

from ..config import Settings
from .base import Listener
from .cron import CronListener
from .cron_rules import DEFAULT_CRON_RULES
from .discord import DiscordListener
from .github_issues import GithubIssuesListener
from .github_pr_review import GithubPrReviewListener
from .telegram import TelegramListener

log = structlog.get_logger(__name__)


def build_listeners(settings: Settings) -> list[Listener]:
    """Construct default listener set from settings.

    Honours ``settings.listeners_enabled`` — empty tuple means 'all'.
    """
    all_listeners: list[Listener] = [
        GithubIssuesListener(
            repo=settings.source_repo,
            label=settings.issue_label,
            poll_sec=settings.github_poll_sec,
        ),
        CronListener(DEFAULT_CRON_RULES),
        DiscordListener(),
    ]
    # GitHub PR review listener — only attached if GITHUB_USER is set.
    if settings.github_user:
        all_listeners.append(
            GithubPrReviewListener(
                user=settings.github_user,
                poll_sec=settings.github_pr_review_poll_sec,
                max_age_days=settings.github_pr_review_max_age_days,
                skip_repos=settings.github_pr_review_skip_repos,
                include_authored=settings.github_pr_review_include_authored,
            )
        )

    # Telegram is optional — only attach if both token and allowlist are set.
    if settings.telegram_bot_token and settings.telegram_allowed_chat_ids:
        all_listeners.append(
            TelegramListener(
                bot_token=settings.telegram_bot_token,
                allowed_chat_ids=settings.telegram_allowed_chat_ids,
                db_path=settings.db_path,
                poll_sec=settings.telegram_poll_sec,
            )
        )
    elif settings.telegram_bot_token or settings.telegram_allowed_chat_ids:
        log.warning(
            "telegram.config_partial",
            has_token=bool(settings.telegram_bot_token),
            has_allowlist=bool(settings.telegram_allowed_chat_ids),
        )

    if not settings.listeners_enabled:
        return all_listeners
    enabled = set(settings.listeners_enabled)
    return [l for l in all_listeners if l.id in enabled]
