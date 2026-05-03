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


def test_list_tasks_sorted_desc_by_id(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    t1 = state.upsert_task(db, _make_task(1))
    t2 = state.upsert_task(db, _make_task(2))
    t3 = state.upsert_task(db, _make_task(3))

    tasks = state.list_tasks(db)

    assert [t.id for t in tasks] == [t3.id, t2.id, t1.id]


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


def test_stage_results_round_trip_by_attempt(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    task = state.upsert_task(db, _make_task())

    state.save_stage_result(db, task.id, Stage.PLAN, {"plan": "do it"})
    state.save_stage_result(
        db, task.id, Stage.IMPLEMENT, {"result": "changed"}, attempt=2
    )

    assert state.get_stage_result(db, task.id, Stage.PLAN) == {"plan": "do it"}
    assert state.get_stage_result(
        db, task.id, Stage.IMPLEMENT, attempt=2
    ) == {"result": "changed"}
    assert state.get_latest_stage_result(db, task.id, Stage.IMPLEMENT) == (
        2,
        {"result": "changed"},
    )
    assert state.list_stage_results(db, task.id, Stage.IMPLEMENT) == [
        (2, {"result": "changed"})
    ]


def test_repo_memory_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)

    state.save_repo_memory(db, "owner/repo", "touched_files", ["src/app.py"])
    state.save_repo_memory(db, "owner/repo", "touched_files", ["src/api.py"])
    state.save_repo_memory(db, "owner/repo", "verify_commands", ["pytest -q"])

    assert state.get_repo_memory(db, "owner/repo", "touched_files") == ["src/api.py"]
    entries = state.list_repo_memory(db, "owner/repo")
    assert [(e["key"], e["value"]) for e in entries] == [
        ("touched_files", ["src/api.py"]),
        ("verify_commands", ["pytest -q"]),
    ]
    assert all(e["updated_at"] for e in entries)


def test_agent_sessions_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    task = state.upsert_task(db, _make_task())

    state.save_agent_session(db, task.id, "implement", "claude_cli", "sess-1")
    state.save_agent_session(db, task.id, "implement", "claude_cli", "sess-2")

    assert (
        state.get_agent_session(db, task.id, "implement", "claude_cli") == "sess-2"
    )
