from __future__ import annotations

import json
from pathlib import Path

from foundry import state
from foundry.models import Stage, Task, TaskStatus


def _make_task(issue_number: int = 1) -> Task:
    return Task(
        repo="owner/repo",
        issue_number=issue_number,
        issue_title=f"issue {issue_number}",
        issue_body="body",
    )


def test_init_creates_schema(tmp_path: Path) -> None:
    db = tmp_path / "foundry.sqlite"
    state.init_db(db)
    assert db.exists()
    # running twice must be idempotent
    state.init_db(db)


def test_upsert_insert_then_update(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    task = _make_task()
    saved = state.upsert_task(db, task)
    assert saved.id is not None

    saved.status = TaskStatus.RUNNING
    saved.current_stage = Stage.IMPLEMENT
    state.upsert_task(db, saved)

    fetched = state.get_task_by_issue(db, "owner/repo", 1)
    assert fetched is not None
    assert fetched.status == TaskStatus.RUNNING
    assert fetched.current_stage == Stage.IMPLEMENT


def test_list_tasks_filter_by_status(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    t1 = state.upsert_task(db, _make_task(1))
    t2 = state.upsert_task(db, _make_task(2))
    t2.status = TaskStatus.DONE
    state.upsert_task(db, t2)

    pending = state.list_tasks(db, TaskStatus.PENDING)
    done = state.list_tasks(db, TaskStatus.DONE)
    assert [t.issue_number for t in pending] == [1]
    assert [t.issue_number for t in done] == [2]


def test_append_log_accumulates(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    task = state.upsert_task(db, _make_task())

    state.append_log(db, task.id, Stage.PLAN, {"steps": 1})
    state.append_log(db, task.id, Stage.IMPLEMENT, {"ok": True})

    fetched = state.get_task(db, task.id)
    logs = json.loads(fetched.logs_json)
    assert len(logs) == 2
    assert logs[0]["stage"] == "plan"
    assert logs[1]["stage"] == "implement"
