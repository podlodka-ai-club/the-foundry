"""Tests for the `telegram_reply` skill.

We don't hit the real Bot API — `httpx.post` is patched. Goal is to verify
ctx-validation (chat_id, token), event recording on success/failure, and
shape of the response dict.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from foundry import state
from foundry.events import read_events
from foundry.models import RunStatus
from foundry.skills.telegram_reply import telegram_reply_impl


@pytest.fixture
def run_ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, int]:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    run_id = state.create_run(
        db,
        automation_id="tg_chat",
        event_id=1,
        session_id="tg-1405827137-tg_chat",
        status=RunStatus.RUNNING,
    )
    monkeypatch.setenv("FOUNDRY_DB_PATH", str(db))
    monkeypatch.setenv("FOUNDRY_RUN_ID", str(run_id))
    monkeypatch.setenv("FOUNDRY_TG_CHAT_ID", "1405827137")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("FOUNDRY_PARENT_EVENT_SEQ", raising=False)
    return db, run_id


def _ok_response(message_id: int = 99) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"ok": True, "result": {"message_id": message_id}}
    return resp


def test_reply_sends_and_records_event(run_ctx: tuple[Path, int]) -> None:
    db, run_id = run_ctx
    with patch("foundry.skills.telegram_reply.httpx.post", return_value=_ok_response(99)) as mock_post:
        out = telegram_reply_impl(text="hi there")

    assert out == {"ok": True, "message_id": 99}
    args, kwargs = mock_post.call_args
    assert "bottest-token" in args[0]
    assert kwargs["json"] == {"chat_id": 1405827137, "text": "hi there"}

    events = read_events(db, run_id=run_id)
    assert len(events) == 1
    assert events[0].stage == "telegram"
    assert events[0].kind == "reply_sent"
    assert events[0].payload["text"] == "hi there"


def test_reply_rejects_empty_text(run_ctx: tuple[Path, int]) -> None:
    out = telegram_reply_impl(text="   ")
    assert out["ok"] is False
    assert "text is required" in out["error"]


def test_reply_fails_when_chat_id_missing(
    run_ctx: tuple[Path, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FOUNDRY_TG_CHAT_ID")
    out = telegram_reply_impl(text="hello")
    assert out["ok"] is False
    assert "FOUNDRY_TG_CHAT_ID" in out["error"]


def test_reply_records_failure_when_api_says_not_ok(run_ctx: tuple[Path, int]) -> None:
    db, run_id = run_ctx
    bad = MagicMock()
    bad.raise_for_status = MagicMock()
    bad.json.return_value = {"ok": False, "description": "chat not found"}
    with patch("foundry.skills.telegram_reply.httpx.post", return_value=bad):
        out = telegram_reply_impl(text="hi")

    assert out["ok"] is False
    events = read_events(db, run_id=run_id)
    assert events[-1].kind == "reply_failed"
