from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_check(client: TestClient) -> None:
    # Act
    response = client.get("/")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_tasks_returns_empty_array(client: TestClient) -> None:
    # Act
    response = client.get("/api/tasks")

    # Assert
    assert response.status_code == 200
    assert response.json() == []


def test_get_task_by_id_returns_404(client: TestClient) -> None:
    # Act
    response = client.get("/api/tasks/1")

    # Assert
    assert response.status_code == 404


def test_get_repos_returns_empty_array(client: TestClient) -> None:
    # Act
    response = client.get("/api/repos")

    # Assert
    assert response.status_code == 200
    assert response.json() == []
