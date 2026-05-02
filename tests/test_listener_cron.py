from __future__ import annotations

import asyncio
from typing import Any

import pytest

from foundry.listeners.cron import (
    CronListener,
    _build_external_id,
    _parse_interval,
)
from foundry.listeners.cron_rules import CronRule


class _RecordingEmit:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        external_id: str,
        kind: str,
        payload: dict[str, Any],
        parent_event_id: int | None = None,
    ) -> int | None:
        self.calls.append(
            {
                "external_id": external_id,
                "kind": kind,
                "payload": payload,
            }
        )
        return len(self.calls)


@pytest.mark.parametrize(
    "schedule,expected",
    [
        ("@every 30s", 30.0),
        ("@every 5m", 300.0),
        ("@every 2h", 7200.0),
    ],
)
def test_parse_interval(schedule: str, expected: float) -> None:
    assert _parse_interval(schedule) == expected


@pytest.mark.parametrize(
    "schedule",
    ["", "every 30s", "@every 30", "@every 30x", "@every -5s"],
)
def test_parse_interval_rejects_malformed(schedule: str) -> None:
    with pytest.raises(ValueError):
        _parse_interval(schedule)


def test_cron_rule_validates_dedup() -> None:
    with pytest.raises(ValueError):
        CronRule(id="r", schedule="@every 60s", dedup="weekly")


def test_build_external_id_tick() -> None:
    a = _build_external_id("r", "tick", "2026-05-02T10:00:00+00:00")
    b = _build_external_id("r", "tick", "2026-05-02T10:00:01+00:00")

    assert a != b


def test_build_external_id_hourly() -> None:
    same_hour_a = _build_external_id("r", "hourly", "2026-05-02T10:00:00+00:00")
    same_hour_b = _build_external_id("r", "hourly", "2026-05-02T10:59:30+00:00")
    diff_hour = _build_external_id("r", "hourly", "2026-05-02T11:00:00+00:00")

    assert same_hour_a == same_hour_b
    assert same_hour_a != diff_hour


def test_build_external_id_daily() -> None:
    same_day_a = _build_external_id("r", "daily", "2026-05-02T01:00:00+00:00")
    same_day_b = _build_external_id("r", "daily", "2026-05-02T23:00:00+00:00")
    diff_day = _build_external_id("r", "daily", "2026-05-03T00:00:00+00:00")

    assert same_day_a == same_day_b
    assert same_day_a != diff_day


async def test_listen_with_no_rules_returns_immediately() -> None:
    listener = CronListener(rules=[])
    emit = _RecordingEmit()

    await asyncio.wait_for(listener.listen(emit), timeout=0.5)

    assert emit.calls == []


async def test_listen_drives_one_rule() -> None:
    rule = CronRule(id="fast", schedule="@every 1s", dedup="tick")
    listener = CronListener(rules=[rule])
    emit = _RecordingEmit()

    # Patch sleep to a no-op so we don't actually wait 1s between ticks.
    real_sleep = asyncio.sleep

    async def fast_sleep(_: float) -> None:
        await real_sleep(0.001)

    import foundry.listeners.cron as cron_mod

    original = cron_mod.asyncio.sleep
    cron_mod.asyncio.sleep = fast_sleep  # type: ignore[assignment]
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(listener.listen(emit), timeout=0.1)
    finally:
        cron_mod.asyncio.sleep = original  # type: ignore[assignment]

    assert len(emit.calls) >= 1
    assert emit.calls[0]["kind"] == "cron.tick"
    assert emit.calls[0]["payload"]["rule_id"] == "fast"
