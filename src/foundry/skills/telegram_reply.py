"""Skill: send a Telegram message back to the chat that triggered the run.

Reads ``FOUNDRY_TG_CHAT_ID`` (set by orchestrator from the trigger event)
and ``TELEGRAM_BOT_TOKEN`` (inherited from the foundry process env) — both
must be present, otherwise the skill returns ``{"ok": False, "error": ...}``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from foundry.events import record_event

_API = "https://api.telegram.org"


def _ctx() -> tuple[Path, int, int | None]:
    db_path = Path(os.environ["FOUNDRY_DB_PATH"])
    run_id = int(os.environ["FOUNDRY_RUN_ID"])
    raw = os.environ.get("FOUNDRY_PARENT_EVENT_SEQ")
    return db_path, run_id, int(raw) if raw else None


def telegram_reply_impl(*, text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "text is required"}

    chat_raw = os.environ.get("FOUNDRY_TG_CHAT_ID", "").strip()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not chat_raw or not token:
        return {
            "ok": False,
            "error": "FOUNDRY_TG_CHAT_ID or TELEGRAM_BOT_TOKEN missing",
        }
    try:
        chat_id = int(chat_raw)
    except ValueError:
        return {"ok": False, "error": f"invalid FOUNDRY_TG_CHAT_ID: {chat_raw!r}"}

    db_path, run_id, parent = _ctx()
    url = f"{_API}/bot{token}/sendMessage"
    try:
        resp = httpx.post(
            url,
            json={"chat_id": chat_id, "text": text},
            timeout=15.0,
        )
        resp.raise_for_status()
        body = resp.json()
    except httpx.HTTPError as exc:
        record_event(
            db_path,
            run_id=run_id,
            stage="telegram",
            kind="reply_failed",
            payload={"error": repr(exc)},
            parent_event_seq=parent,
        )
        return {"ok": False, "error": f"http error: {exc}"}

    if not body.get("ok"):
        record_event(
            db_path,
            run_id=run_id,
            stage="telegram",
            kind="reply_failed",
            payload={"response": body},
            parent_event_seq=parent,
        )
        return {"ok": False, "error": f"telegram api: {body!r}"}

    message_id = (body.get("result") or {}).get("message_id")
    record_event(
        db_path,
        run_id=run_id,
        stage="telegram",
        kind="reply_sent",
        payload={"chat_id": chat_id, "text": text, "message_id": message_id},
        parent_event_seq=parent,
    )
    return {"ok": True, "message_id": message_id}


__all__ = ["telegram_reply_impl"]
