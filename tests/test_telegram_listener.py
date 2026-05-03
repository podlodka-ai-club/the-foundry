"""Tests for `TelegramListener` admit logic + offset resume.

The HTTP layer is intentionally not exercised here — we drive `_admit` and
`_resume_offset` directly because they encode all the policy. Network code
is a thin wrapper that we'll smoke-test once against the live bot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry import state
from foundry.listeners.telegram import TelegramListener


def _listener(tmp_path: Path, allowed: tuple[int, ...] = (1405827137,)) -> TelegramListener:
    return TelegramListener(
        bot_token="dummy",
        allowed_chat_ids=allowed,
        db_path=tmp_path / "f.sqlite",
        poll_sec=1,
    )


def _make_update(
    *,
    update_id: int = 1,
    chat_id: int = 1405827137,
    chat_type: str = "private",
    text: str | None = "hi",
    user_id: int = 9001,
    username: str | None = "alice",
) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 42,
            "date": 1700000000,
            "chat": {"id": chat_id, "type": chat_type},
            "from": {"id": user_id, "username": username, "first_name": "Alice"},
            "text": text,
        },
    }


def test_admit_passes_private_message_from_allowlisted_chat(tmp_path: Path) -> None:
    listener = _listener(tmp_path)
    payload = listener._admit(_make_update(text="hello"))
    assert payload is not None
    assert payload["chat_id"] == 1405827137
    assert payload["text"] == "hello"
    assert payload["username"] == "alice"


def test_admit_drops_chat_outside_allowlist(tmp_path: Path) -> None:
    listener = _listener(tmp_path, allowed=(999,))
    assert listener._admit(_make_update()) is None


def test_admit_drops_group_chat(tmp_path: Path) -> None:
    listener = _listener(tmp_path)
    assert listener._admit(_make_update(chat_type="group")) is None


def test_admit_drops_empty_text(tmp_path: Path) -> None:
    listener = _listener(tmp_path)
    assert listener._admit(_make_update(text="")) is None
    assert listener._admit(_make_update(text="   ")) is None
    assert listener._admit(_make_update(text=None)) is None


def test_admit_drops_non_message_updates(tmp_path: Path) -> None:
    listener = _listener(tmp_path)
    # e.g. callback_query, edited_message — anything without a top-level "message".
    assert listener._admit({"update_id": 1, "callback_query": {}}) is None


def test_resume_offset_returns_none_on_empty_db(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    listener = _listener(tmp_path)
    listener.db_path = db
    assert listener._resume_offset() is None


def test_resume_offset_returns_last_plus_one(tmp_path: Path) -> None:
    from foundry.events import dispatch_event

    db = tmp_path / "f.sqlite"
    state.init_db(db)
    dispatch_event(
        db, trigger_id="telegram.message", dedupe_key="100", payload={}
    )
    dispatch_event(
        db, trigger_id="telegram.message", dedupe_key="105", payload={}
    )
    listener = _listener(tmp_path)
    listener.db_path = db
    assert listener._resume_offset() == 106


def test_resume_offset_handles_non_int_external_id(tmp_path: Path) -> None:
    """Defensive: state.last_external_id may return junk if data was migrated;
    we should fall through to None rather than crash."""
    from foundry.events import dispatch_event

    db = tmp_path / "f.sqlite"
    state.init_db(db)
    dispatch_event(
        db,
        trigger_id="telegram.message",
        dedupe_key="not-a-number",
        payload={},
    )
    listener = _listener(tmp_path)
    listener.db_path = db
    assert listener._resume_offset() is None


def test_listener_requires_token() -> None:
    with pytest.raises(ValueError, match="bot_token"):
        TelegramListener(
            bot_token="",
            allowed_chat_ids=(1,),
            db_path=Path("/tmp/x.sqlite"),
        )
