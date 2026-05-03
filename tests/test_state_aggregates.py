from __future__ import annotations

from pathlib import Path

from foundry.events import dispatch_event
from foundry.models import RunStatus
from foundry.state import (
    count_runs_by_automation_status,
    create_run,
    init_db,
    last_event_at_by_trigger,
    update_run,
)


def test_count_runs_by_automation_status_aggregates(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    init_db(db)
    r1 = create_run(db, automation_id="dev_task", event_id=1, session_id="s1")
    r2 = create_run(db, automation_id="dev_task", event_id=2, session_id="s2")
    r3 = create_run(db, automation_id="other", event_id=3, session_id="s3")
    update_run(db, r2, status=RunStatus.DONE)
    update_run(db, r3, status=RunStatus.FAILED)

    # Act
    counts = count_runs_by_automation_status(db)

    # Assert
    assert counts[("dev_task", "running")] == 1
    assert counts[("dev_task", "done")] == 1
    assert counts[("other", "failed")] == 1
    assert ("dev_task", "running") in counts
    assert sum(counts.values()) == 3
    assert isinstance(r1, int)


def test_last_event_at_by_trigger_returns_max(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    init_db(db)
    dispatch_event(
        db,
        trigger_id="github_issues.issue_opened",
        dedupe_key="repo#1",
        payload={"x": 1},
    )
    dispatch_event(
        db,
        trigger_id="github_issues.issue_opened",
        dedupe_key="repo#2",
        payload={"x": 2},
    )
    dispatch_event(
        db,
        trigger_id="cron.nightly",
        dedupe_key="cron-nightly-2026-05-02T00:00",
        payload={"tick_at": "2026-05-02T00:00:00Z"},
    )

    # Act
    last = last_event_at_by_trigger(db)

    # Assert
    assert "github_issues.issue_opened" in last
    assert "cron.nightly" in last
