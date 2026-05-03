from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from foundry.events import dispatch_event
from foundry.state import get_event, init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "events.sqlite"
    init_db(path)
    return path


def test_dispatch_event_inserts_with_split_source_kind(db_path: Path) -> None:
    """``trigger_id`` is split on the first dot into ``source``/``kind`` so
    legacy display code keeps working."""
    event_id = dispatch_event(
        db_path,
        trigger_id="github_issues.issue_opened",
        dedupe_key="owner/repo#1",
        payload={"title": "hello"},
    )

    assert event_id == 1
    fetched = get_event(db_path, event_id)
    assert fetched is not None
    assert fetched.source == "github_issues"
    assert fetched.external_id == "owner/repo#1"
    assert fetched.kind == "issue_opened"
    assert fetched.payload == {"title": "hello"}


def test_dispatch_event_dedupes(db_path: Path) -> None:
    first = dispatch_event(
        db_path,
        trigger_id="github_issues.issue_opened",
        dedupe_key="owner/repo#1",
        payload={"title": "hello"},
    )
    second = dispatch_event(
        db_path,
        trigger_id="github_issues.issue_opened",
        dedupe_key="owner/repo#1",
        payload={"title": "hello"},
    )

    assert isinstance(first, int)
    assert second is None

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 1


def test_dispatch_event_different_triggers_independent(db_path: Path) -> None:
    """Same ``dedupe_key`` under different triggers does NOT collapse — the
    UNIQUE constraint is over ``(trigger_id, external_id)``."""
    a = dispatch_event(
        db_path,
        trigger_id="github_issues.issue_opened",
        dedupe_key="1",
        payload={},
    )
    b = dispatch_event(
        db_path,
        trigger_id="cron.nightly",
        dedupe_key="1",
        payload={"rule_id": "nightly"},
    )

    assert a is not None
    assert b is not None
    assert a != b


def test_dispatch_event_serializes_payload(db_path: Path) -> None:
    payload = {"a": 1, "b": [2, 3], "nested": {"x": "y"}}
    event_id = dispatch_event(
        db_path,
        trigger_id="github_issues.issue_opened",
        dedupe_key="owner/repo#42",
        payload=payload,
    )

    fetched = get_event(db_path, event_id)
    assert fetched is not None
    assert fetched.payload == payload


def test_get_event_missing_returns_none(db_path: Path) -> None:
    assert get_event(db_path, 999) is None
