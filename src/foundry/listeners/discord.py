from __future__ import annotations

import asyncio

import structlog

from .base import EmitFn

log = structlog.get_logger(__name__)


class DiscordListener:
    """Idle stub. Real implementation lands in a later change."""

    id = "discord"
    source = "discord"

    async def listen(self, emit: EmitFn) -> None:
        log.info("listener.discord.stub_started")
        await asyncio.Event().wait()
