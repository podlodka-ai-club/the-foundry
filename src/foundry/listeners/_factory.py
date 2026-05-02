from __future__ import annotations

from ..config import Settings
from .base import Listener
from .cron import CronListener
from .cron_rules import DEFAULT_CRON_RULES
from .discord import DiscordListener
from .github_issues import GithubIssuesListener


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
    if not settings.listeners_enabled:
        return all_listeners
    enabled = set(settings.listeners_enabled)
    return [l for l in all_listeners if l.id in enabled]
