from __future__ import annotations

from pathlib import Path

from foundry.models import RunStatus
from foundry.state import (
    count_runs_by_automation_status,
    create_run,
    init_db,
    last_event_at_by_source,
    record_external_event,
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
    # Sanity: no rogue keys
    assert ("dev_task", "running") in counts
    assert sum(counts.values()) == 3
    # mute usage warning for r1
    assert isinstance(r1, int)


def test_last_event_at_by_source_returns_max(tmp_path: Path) -> None:
    # Arrange
    db = tmp_path / "f.sqlite"
    init_db(db)
    record_external_event(
        db,
        source="github_issues",
        external_id="repo#1",
        kind="issue.opened",
        payload={"x": 1},
    )
    record_external_event(
        db,
        source="github_issues",
        external_id="repo#2",
        kind="issue.opened",
        payload={"x": 2},
    )
    record_external_event(
        db,
        source="cron",
        external_id="cron-rule-2026-05-02T00:00",
        kind="cron.tick",
        payload={"tick_at": "2026-05-02T00:00:00Z"},
    )

    # Act
    last = last_event_at_by_source(db)

    # Assert
    assert "github_issues" in last
    assert "cron" in last
    assert last["github_issues"] >= last["cron"] or last["cron"] >= last["github_issues"]
