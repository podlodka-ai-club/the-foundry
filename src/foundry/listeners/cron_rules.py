"""Cron schedule rules.

Trigger naming convention (used by C4 orchestrator):
- ``cron:nightly_cleanup`` — automation подписана на rule с id 'nightly_cleanup'.

CronRule.dedup options:
- ``tick`` — каждый tick новый external_id (новая сессия каждый раз)
- ``hourly`` — один external_id в час (одна сессия на час)
- ``daily`` — один в день
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CronRule:
    id: str
    schedule: str  # "@every 60s" / "@every 5m" / "@every 2h"
    dedup: str = "tick"

    def __post_init__(self) -> None:
        if self.dedup not in {"tick", "hourly", "daily"}:
            raise ValueError(f"invalid dedup: {self.dedup!r}")


DEFAULT_CRON_RULES: list[CronRule] = []
