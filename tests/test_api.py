from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from api.main import app, get_db_path
from foundry import state
from foundry.events import record_event
from foundry.models import FailureKind, RunStatus


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    db = tmp_path / "f.sqlite"
    state.init_db(db)
    return db


@pytest.fixture
def client(db_path: Path) -> Iterator[TestClient]:
    app.dependency_overrides[get_db_path] = lambda: db_path
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db_path, None)


# --- Health -----------------------------------------------------------------


def test_health_check(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- Automations ------------------------------------------------------------


def test_get_automations_returns_list(client: TestClient) -> None:
    # Act
    response = client.get("/api/automations")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert {a["id"] for a in body} >= {"dev_task"}


def test_get_automations_counts_match_db(client: TestClient, db_path: Path) -> None:
    # Arrange — one running run for dev_task
    event_id = state.record_external_event(
        db_path,
        source="github_issues",
        external_id="repo#1",
        kind="issue.opened",
        payload={"title": "demo", "number": 1},
    )
    assert event_id is not None
    state.create_run(
        db_path,
        automation_id="dev_task",
        event_id=event_id,
        session_id="s1",
        status=RunStatus.RUNNING,
    )

    # Act
    response = client.get("/api/automations")

    # Assert
    assert response.status_code == 200
    by_id = {a["id"]: a for a in response.json()}
    counts = by_id["dev_task"]["counts"]
    assert counts["running"] == 1
    assert counts["total"] == 1


# --- Triggers ---------------------------------------------------------------


def test_get_triggers_returns_list_with_known(client: TestClient) -> None:
    response = client.get("/api/triggers")
    assert response.status_code == 200
    body = response.json()
    sources = {t["source"] for t in body}
    # Listener factory always builds at least github_issues, cron, discord —
    # but the env-based config may strip some. Guarantee the wire shape:
    assert isinstance(body, list)
    for t in body:
        assert {"id", "source", "kind", "last_seen", "health"} <= set(t.keys())
    # We expect github_issues to be present in defaults.
    assert "github_issues" in sources


def test_get_triggers_health_null_when_no_events(client: TestClient) -> None:
    response = client.get("/api/triggers")
    assert response.status_code == 200
    by_source = {t["source"]: t for t in response.json()}
    assert by_source["github_issues"]["last_seen"] is None
    assert by_source["github_issues"]["health"] is None


def test_get_triggers_health_ok_after_recent_event(
    client: TestClient, db_path: Path
) -> None:
    state.record_external_event(
        db_path,
        source="github_issues",
        external_id="repo#42",
        kind="issue.opened",
        payload={"title": "x"},
    )

    response = client.get("/api/triggers")
    by_source = {t["source"]: t for t in response.json()}
    assert by_source["github_issues"]["last_seen"] is not None
    assert by_source["github_issues"]["health"] == "ok"


# --- Runs list --------------------------------------------------------------


def _seed_event(db_path: Path, *, source: str = "github_issues", external_id: str = "repo#1") -> int:
    eid = state.record_external_event(
        db_path,
        source=source,
        external_id=external_id,
        kind="issue.opened",
        payload={"title": f"demo-{external_id}", "number": 1},
    )
    assert eid is not None
    return eid


def test_get_runs_no_filter_returns_all(client: TestClient, db_path: Path) -> None:
    e1 = _seed_event(db_path, external_id="repo#1")
    e2 = _seed_event(db_path, external_id="repo#2")
    state.create_run(db_path, automation_id="dev_task", event_id=e1, session_id="s1")
    state.create_run(db_path, automation_id="dev_task", event_id=e2, session_id="s2")

    response = client.get("/api/runs")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2


def test_get_runs_filter_running(client: TestClient, db_path: Path) -> None:
    e1 = _seed_event(db_path, external_id="repo#1")
    e2 = _seed_event(db_path, external_id="repo#2")
    r1 = state.create_run(db_path, automation_id="dev_task", event_id=e1, session_id="s1")
    state.create_run(db_path, automation_id="dev_task", event_id=e2, session_id="s2")
    state.update_run(db_path, r1, status=RunStatus.DONE)

    response = client.get("/api/runs?filter=running")
    assert response.status_code == 200
    body = response.json()
    statuses = {r["status"] for r in body}
    assert statuses == {"running"}


def test_get_runs_filter_failed_includes_unclear(
    client: TestClient, db_path: Path
) -> None:
    e1 = _seed_event(db_path, external_id="repo#1")
    e2 = _seed_event(db_path, external_id="repo#2")
    e3 = _seed_event(db_path, external_id="repo#3")
    r1 = state.create_run(db_path, automation_id="dev_task", event_id=e1, session_id="s1")
    r2 = state.create_run(db_path, automation_id="dev_task", event_id=e2, session_id="s2")
    state.create_run(db_path, automation_id="dev_task", event_id=e3, session_id="s3")
    state.update_run(db_path, r1, status=RunStatus.FAILED)
    state.update_run(db_path, r2, status=RunStatus.UNCLEAR)

    response = client.get("/api/runs?filter=failed")
    assert response.status_code == 200
    statuses = {r["status"] for r in response.json()}
    assert statuses == {"failed", "unclear"}


def test_get_run_by_id_includes_events(client: TestClient, db_path: Path) -> None:
    eid = _seed_event(db_path)
    rid = state.create_run(
        db_path, automation_id="dev_task", event_id=eid, session_id="s1"
    )
    record_event(db_path, rid, "plan", "agent_text", {"text": "hello"})

    response = client.get(f"/api/runs/{rid}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == rid
    assert len(body["events"]) == 1
    assert body["events"][0]["kind"] == "agent_text"
    assert body["trigger"] is not None
    assert body["trigger"]["source"] == "github_issues"


def test_get_run_by_id_404_for_missing(client: TestClient) -> None:
    response = client.get("/api/runs/99999")
    assert response.status_code == 404


# --- Stop / Retry / Messages ----------------------------------------------


def test_post_runs_stop_updates_status(
    client: TestClient, db_path: Path
) -> None:
    eid = _seed_event(db_path)
    rid = state.create_run(
        db_path, automation_id="dev_task", event_id=eid, session_id="s1"
    )

    response = client.post(f"/api/runs/{rid}/stop")
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    run = state.get_run(db_path, rid)
    assert run is not None
    assert run.status is RunStatus.FAILED
    assert run.failure_kind is FailureKind.INFRA
    assert run.failure_msg == "stopped by user"


def test_post_runs_stop_409_when_terminal(
    client: TestClient, db_path: Path
) -> None:
    eid = _seed_event(db_path)
    rid = state.create_run(
        db_path, automation_id="dev_task", event_id=eid, session_id="s1"
    )
    state.update_run(db_path, rid, status=RunStatus.DONE)

    response = client.post(f"/api/runs/{rid}/stop")
    assert response.status_code == 409


def test_post_runs_retry_creates_pending_run(
    client: TestClient, db_path: Path
) -> None:
    eid = _seed_event(db_path)
    rid = state.create_run(
        db_path, automation_id="dev_task", event_id=eid, session_id="sX"
    )
    state.update_run(db_path, rid, status=RunStatus.FAILED)

    response = client.post(f"/api/runs/{rid}/retry")
    assert response.status_code == 200
    body = response.json()
    new_id = body["run_id"]
    new_run = state.get_run(db_path, new_id)
    assert new_run is not None
    assert new_run.status is RunStatus.PENDING
    assert new_run.session_id == "sX"
    assert new_run.session_seq == 2


def test_post_runs_retry_409_when_running(
    client: TestClient, db_path: Path
) -> None:
    eid = _seed_event(db_path)
    rid = state.create_run(
        db_path, automation_id="dev_task", event_id=eid, session_id="sX"
    )

    response = client.post(f"/api/runs/{rid}/retry")
    assert response.status_code == 409


def test_post_runs_messages_writes_breadcrumb(
    client: TestClient, db_path: Path
) -> None:
    eid = _seed_event(db_path)
    rid = state.create_run(
        db_path, automation_id="dev_task", event_id=eid, session_id="s1"
    )

    response = client.post(
        f"/api/runs/{rid}/messages",
        json={"type": "enqueue", "text": "please continue"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["ok"] is True
    assert isinstance(body["seq"], int)

    from foundry.events import read_events

    evs = read_events(db_path, rid)
    user_msgs = [e for e in evs if e.kind == "user_message"]
    assert len(user_msgs) == 1
    assert user_msgs[0].stage == "user_input"
    assert user_msgs[0].payload["type"] == "enqueue"
    assert user_msgs[0].payload["text"] == "please continue"


# --- Automation runs --------------------------------------------------------


def test_get_automation_runs_404_for_unknown(client: TestClient) -> None:
    response = client.get("/api/automations/__nope__/runs")
    assert response.status_code == 404


def test_get_automation_runs_filters_by_automation(
    client: TestClient, db_path: Path
) -> None:
    e1 = _seed_event(db_path, external_id="repo#1")
    e2 = _seed_event(db_path, external_id="repo#2")
    state.create_run(db_path, automation_id="dev_task", event_id=e1, session_id="s1")
    state.create_run(db_path, automation_id="other", event_id=e2, session_id="s2")

    response = client.get("/api/automations/dev_task/runs")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["automation_id"] == "dev_task"


# Touch time module for unused import lint
_ = time
