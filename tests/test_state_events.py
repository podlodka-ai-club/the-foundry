from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from foundry.state import (
    get_event,
    init_db,
    read_events_after,
    record_external_event,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "events.sqlite"
    init_db(path)
    return path


def test_record_external_event_inserts(db_path: Path) -> None:
    event_id = record_external_event(
        db_path,
        source="github_issues",
        external_id="owner/repo#1",
        kind="issue.opened",
        payload={"title": "hello"},
    )

    assert event_id == 1
    fetched = get_event(db_path, event_id)
    assert fetched is not None
    assert fetched.source == "github_issues"
    assert fetched.external_id == "owner/repo#1"
    assert fetched.kind == "issue.opened"
    assert fetched.payload == {"title": "hello"}


def test_record_external_event_dedupes(db_path: Path) -> None:
    first = record_external_event(
        db_path,
        source="github_issues",
        external_id="owner/repo#1",
        kind="issue.opened",
        payload={"title": "hello"},
    )
    second = record_external_event(
        db_path,
        source="github_issues",
        external_id="owner/repo#1",
        kind="issue.opened",
        payload={"title": "hello"},
    )

    assert isinstance(first, int)
    assert second is None

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 1


def test_record_external_event_different_sources_independent(db_path: Path) -> None:
    a = record_external_event(
        db_path,
        source="github_issues",
        external_id="1",
        kind="issue.opened",
        payload={},
    )
    b = record_external_event(
        db_path,
        source="cron",
        external_id="1",
        kind="cron.tick",
        payload={},
    )

    assert a is not None
    assert b is not None
    assert a != b


def test_record_external_event_serializes_payload(db_path: Path) -> None:
    payload = {"a": 1, "b": [2, 3], "nested": {"x": "y"}}
    event_id = record_external_event(
        db_path,
        source="github_issues",
        external_id="owner/repo#42",
        kind="issue.opened",
        payload=payload,
    )

    fetched = get_event(db_path, event_id)
    assert fetched is not None
    assert fetched.payload == payload


def test_read_events_after_filters_and_limits(db_path: Path) -> None:
    for i in range(1, 6):
        record_external_event(
            db_path,
            source="github_issues",
            external_id=f"r#{i}",
            kind="issue.opened",
            payload={},
        )

    events = read_events_after(db_path, after_id=2, limit=2)

    assert [e.id for e in events] == [3, 4]


def test_read_events_after_default_returns_all(db_path: Path) -> None:
    for i in range(1, 4):
        record_external_event(
            db_path,
            source="github_issues",
            external_id=f"r#{i}",
            kind="issue.opened",
            payload={},
        )

    events = read_events_after(db_path)

    assert [e.id for e in events] == [1, 2, 3]


def test_get_event_missing_returns_none(db_path: Path) -> None:
    assert get_event(db_path, 999) is None
