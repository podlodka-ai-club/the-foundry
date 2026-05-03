from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from foundry import state
from foundry.events import record_event
from foundry.models import Stage, Task, TaskStatus


@pytest.fixture
def _setup_env(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "test.sqlite"
    monkeypatch.setenv("SOURCE_REPO", "test/repo")
    monkeypatch.setenv("TARGET_REPO", "test/repo")
    monkeypatch.setenv("DB_PATH", str(db_path))
    state.init_db(db_path)
    return db_path


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_check(client: TestClient) -> None:
    # Act
    response = client.get("/")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_tasks_empty(client: TestClient, _setup_env: Path) -> None:
    # Act
    response = client.get("/api/tasks")

    # Assert
    assert response.status_code == 200
    assert response.json() == []


def test_get_tasks_returns_ui_tasks(client: TestClient, _setup_env: Path) -> None:
    # Arrange
    db = _setup_env
    task = state.upsert_task(
        db,
        Task(
            repo="owner/repo",
            issue_number=42,
            issue_title="Test issue",
            issue_body="Body",
        ),
    )
    record_event(db, task.id, "plan", "stage_started", {"agent": {"name": "stub"}})
    record_event(
        db,
        task.id,
        "plan",
        "stage_finished",
        {"duration_ms": 100, "cost_usd": 0.05, "tokens_in": 10, "tokens_out": 20},
    )

    # Act
    response = client.get("/api/tasks")

    # Assert
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list) and len(payload) == 1
    item = payload[0]
    assert item["issue_number"] == 42
    assert item["status"] == "pending"
    assert item["events"] is None
    assert item["stages"]["agent_plan"]["status"] == "done"
    assert item["stages"]["agent_plan"]["cost_usd"] == 0.05
    assert item["total_cost_usd"] == 0.05
    assert item["tokens_in_total"] == 10
    assert item["tokens_out_total"] == 20
    assert item["duration_ms_total"] == 100


def test_get_task_detail_includes_events(client: TestClient, _setup_env: Path) -> None:
    # Arrange
    db = _setup_env
    task = state.upsert_task(
        db,
        Task(
            repo="owner/repo",
            issue_number=7,
            issue_title="Detail test",
            issue_body="Body",
        ),
    )
    record_event(db, task.id, "plan", "stage_started", {})
    record_event(db, task.id, "plan", "agent_text", {"text": "hello"})
    record_event(db, task.id, "plan", "stage_finished", {"duration_ms": 1})

    # Act
    response = client.get(f"/api/tasks/{task.id}")

    # Assert
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == task.id
    assert payload["events"] is not None
    assert len(payload["events"]) == 3
    assert payload["events"][0]["stage"] == "agent_plan"


def test_get_task_detail_404(client: TestClient, _setup_env: Path) -> None:
    # Act
    response = client.get("/api/tasks/999")

    # Assert
    assert response.status_code == 404


def test_reset_task_sets_pending_fetch(client: TestClient, _setup_env: Path) -> None:
    # Arrange
    db = _setup_env
    task = state.upsert_task(
        db,
        Task(
            repo="owner/repo",
            issue_number=9,
            issue_title="Failed task",
            issue_body="Body",
            status=TaskStatus.FAILED,
            current_stage=Stage.FAILED,
            pr_url="https://example.test/pr/1",
        ),
    )

    # Act
    response = client.post(f"/api/tasks/{task.id}/reset")

    # Assert
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["current_stage"] == "fetch"
    assert payload["pr_url"] is None


def test_reset_task_rejects_running(client: TestClient, _setup_env: Path) -> None:
    # Arrange
    db = _setup_env
    task = state.upsert_task(
        db,
        Task(
            repo="owner/repo",
            issue_number=10,
            issue_title="Running task",
            issue_body="Body",
            status=TaskStatus.RUNNING,
            current_stage=Stage.IMPLEMENT,
        ),
    )

    # Act
    response = client.post(f"/api/tasks/{task.id}/reset")

    # Assert
    assert response.status_code == 409


def test_get_repos_counts(client: TestClient, _setup_env: Path) -> None:
    # Arrange
    db = _setup_env
    t1 = state.upsert_task(
        db,
        Task(
            repo="owner/repo",
            issue_number=1,
            issue_title="A",
            issue_body="",
        ),
    )
    t2 = state.upsert_task(
        db,
        Task(
            repo="owner/repo",
            issue_number=2,
            issue_title="B",
            issue_body="",
        ),
    )
    t3 = state.upsert_task(
        db,
        Task(
            repo="owner/repo",
            issue_number=3,
            issue_title="C",
            issue_body="",
        ),
    )
    t2.status = TaskStatus.DONE
    state.upsert_task(db, t2)
    t3.status = TaskStatus.FAILED
    state.upsert_task(db, t3)
    _ = t1  # stays PENDING

    # Act
    response = client.get("/api/repos")

    # Assert
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    entry = payload[0]
    assert entry["repo"] == "owner/repo"
    assert entry["counts"] == {"RUNNING": 0, "DONE": 1, "FAILED": 1, "PENDING": 1}
