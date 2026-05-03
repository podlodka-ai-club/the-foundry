"""Telegram bot listener — long-poll Bot API ``getUpdates``.

Emits one ``message`` event per incoming text message from a private chat
whose ``chat.id`` is in the allowlist. ``external_id`` is the Telegram
``update_id`` (stringified) so dedup is handled by the events table's
``UNIQUE(source, external_id)`` constraint, and the listener can resume
after restart by reading the highest ``external_id`` for ``source="telegram"``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import structlog

from .. import state, triggers
from .base import EmitFn

log = structlog.get_logger(__name__)

_API = "https://api.telegram.org"


class TelegramListener:
    id = "telegram"
    source = "telegram"

    def __init__(
        self,
        *,
        bot_token: str,
        allowed_chat_ids: tuple[int, ...],
        db_path: Path,
        poll_sec: int = 25,
    ) -> None:
        if not bot_token:
            raise ValueError("TelegramListener requires a non-empty bot_token")
        self.bot_token = bot_token
        self.allowed = set(allowed_chat_ids)
        self.db_path = db_path
        self.poll_sec = poll_sec
        self._offset: int | None = None

    def _resume_offset(self) -> int | None:
        """Read the largest update_id we've already emitted, so we can
        ack-ahead via getUpdates(offset=last+1) on first poll."""
        last = state.last_external_id(self.db_path, self.source)
        if not last:
            return None
        try:
            return int(last) + 1
        except ValueError:
            return None

    async def _get_updates(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeout": self.poll_sec,
            "allowed_updates": '["message"]',
        }
        if self._offset is not None:
            params["offset"] = self._offset
        url = f"{_API}/bot{self.bot_token}/getUpdates"
        # HTTP timeout = poll + buffer so the server-side long-poll can
        # fully use its window before we abort.
        resp = await client.get(url, params=params, timeout=self.poll_sec + 10)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("ok"):
            raise RuntimeError(f"telegram getUpdates failed: {body!r}")
        return list(body.get("result") or [])

    def _admit(self, update: dict[str, Any]) -> dict[str, Any] | None:
        """Return a normalized payload for emission, or None to drop."""
        msg = update.get("message")
        if not isinstance(msg, dict):
            return None
        text = msg.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if not isinstance(chat_id, int) or chat_id not in self.allowed:
            return None
        if chat.get("type") != "private":
            return None
        sender = msg.get("from") or {}
        username = sender.get("username")
        first_name = sender.get("first_name")
        if isinstance(username, str) and username:
            short_name = f"@{username}"
        elif isinstance(first_name, str) and first_name:
            short_name = first_name
        else:
            short_name = None
        return {
            "chat_id": chat_id,
            "user_id": sender.get("id"),
            "username": username,
            "first_name": first_name,
            "short_name": short_name,
            "text": text,
            "message_id": msg.get("message_id"),
            "date": msg.get("date"),
        }

    async def tick_once(self, emit: EmitFn, client: httpx.AsyncClient) -> None:
        if self._offset is None:
            self._offset = self._resume_offset()
        updates = await self._get_updates(client)
        for upd in updates:
            update_id = upd.get("update_id")
            if not isinstance(update_id, int):
                continue
            # Always advance offset, even for filtered-out updates, so we
            # don't re-fetch them on next poll.
            self._offset = update_id + 1
            payload = self._admit(upd)
            if payload is None:
                log.debug("telegram.update_dropped", update_id=update_id)
                continue
            await emit(
                trigger_id=triggers.TELEGRAM_MESSAGE,
                dedupe_key=str(update_id),
                payload=payload,
            )

    async def listen(self, emit: EmitFn) -> None:
        if not self.allowed:
            log.warning("telegram.no_allowlist_skipping")
            await asyncio.Event().wait()  # pragma: no cover — safe idle
            return
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    await self.tick_once(emit, client)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("listener.tick.error", listener=self.id)
                    await asyncio.sleep(2.0)
