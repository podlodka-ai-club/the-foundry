"""Pydantic v2 contract for the C6 web UI.

All wire types live here. Mirrors `web/src/api/types.ts`. Use `model_dump()`
when serialising and `model_validate()` when accepting external dicts.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class UiAutomationCounts(BaseModel):
    running: int = 0
    waiting: int = 0
    pending: int = 0
    total: int = 0


class UiAutomation(BaseModel):
    id: str
    name: str
    description: str
    triggers: list[str]
    agent: dict[str, Any]
    counts: UiAutomationCounts


class UiTrigger(BaseModel):
    id: str
    source: str
    kind: str
    last_seen: str | None = None
    health: Literal["ok", "stale"] | None = None


class UiRunTrigger(BaseModel):
    source: str
    external_id: str
    text: str
    author: str | None = None
    short_name: str | None = None
    repo: str | None = None
    kind: str


class UiRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    automation_id: str
    event_id: int
    session_id: str
    session_seq: int
    status: str
    started_at: str
    finished_at: str | None = None
    duration_sec: float | None = None
    cost_usd: float | None = None
    failure_kind: str | None = None
    failure_msg: str | None = None
    waiting_reason: str | None = None
    outcome: str | None = None
    agent_session_id: str | None = None
    trigger: UiRunTrigger | None = None


class UiEvent(BaseModel):
    seq: int
    run_id: int
    stage: str
    kind: str
    ts_ms: int
    payload: dict[str, Any]
    parent_event_seq: int | None = None


class UiRunDetail(UiRun):
    events: list[UiEvent] = []


class PostMessageBody(BaseModel):
    type: Literal["continue", "enqueue", "reply"]
    text: str
