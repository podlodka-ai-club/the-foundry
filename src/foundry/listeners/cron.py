from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

import structlog

from .base import EmitFn
from .cron_rules import CronRule

log = structlog.get_logger(__name__)

_INTERVAL_RE = re.compile(r"^@every (\d+)([smh])$")
_MULT = {"s": 1, "m": 60, "h": 3600}


def _parse_interval(schedule: str) -> float:
    m = _INTERVAL_RE.match(schedule)
    if not m:
        raise ValueError(f"invalid schedule: {schedule!r}")
    return float(m.group(1)) * _MULT[m.group(2)]


def _build_dedupe_key(rule_id: str, dedup: str, tick_iso: str) -> str:
    if dedup == "tick":
        return f"cron-{rule_id}-{tick_iso}"
    if dedup == "hourly":
        return f"cron-{rule_id}-{tick_iso[:13]}"
    if dedup == "daily":
        return f"cron-{rule_id}-{tick_iso[:10]}"
    raise ValueError(dedup)


class CronListener:
    """Drives a fixed list of :class:`CronRule` and emits one event per tick.

    Each rule emits under its own ``cron.<rule_id>`` trigger id — automations
    subscribe to the rule they care about, no central matcher needed.
    """

    id = "cron"
    source = "cron"

    def __init__(self, rules: list[CronRule]) -> None:
        self.rules = rules

    async def listen(self, emit: EmitFn) -> None:
        if not self.rules:
            return
        await asyncio.gather(*(self._run_rule(r, emit) for r in self.rules))

    async def _run_rule(self, rule: CronRule, emit: EmitFn) -> None:
        interval = _parse_interval(rule.schedule)
        while True:
            try:
                await self._emit_tick(rule, emit)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("listener.cron.tick.error", rule=rule.id)
            await asyncio.sleep(interval)

    async def _emit_tick(self, rule: CronRule, emit: EmitFn) -> None:
        tick_iso = datetime.now(timezone.utc).isoformat()
        await emit(
            trigger_id=f"cron.{rule.id}",
            dedupe_key=_build_dedupe_key(rule.id, rule.dedup, tick_iso),
            payload={"rule_id": rule.id, "tick_at": tick_iso, "short_name": rule.id},
        )
