from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from foundry.models import Event, Task

# Aliases applied at the projection boundary only. DB and pipeline keep the
# internal FSM names (`plan`, `implement`, `verify`, ...).
STAGE_ALIAS: dict[str, str] = {
    "plan": "agent_plan",
    "implement": "agent_implement",
}


def alias_stage(internal: str) -> str:
    """Return the UI-facing name for an internal FSM stage name."""
    return STAGE_ALIAS.get(internal, internal)


StageStatus = Literal["pending", "running", "done", "failed"]


class UiStage(BaseModel):
    name: str
    status: StageStatus
    duration_ms: int | None = None
    cost_usd: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    agent: dict[str, Any] | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error: str | None = None


class UiEvent(BaseModel):
    seq: int
    stage: str
    kind: str
    ts_ms: int
    payload: dict[str, Any]


class UiMemoryEntry(BaseModel):
    repo: str
    key: str
    value: Any
    updated_at: str


class UiTask(BaseModel):
    id: int
    repo: str
    issue_number: int
    issue_title: str
    status: str
    current_stage: str
    attempts: int
    pr_url: str | None = None
    branch_name: str | None = None
    worktree_path: str | None = None
    updated_at: str | None = None
    created_at: str | None = None
    total_cost_usd: float = 0.0
    tokens_in_total: int = 0
    tokens_out_total: int = 0
    duration_ms_total: int = 0
    stages: dict[str, UiStage] = Field(default_factory=dict)
    memory: list[UiMemoryEntry] = Field(default_factory=list)
    events: list[UiEvent] | None = None


def project_task(
    task: Task,
    events: list[Event],
    *,
    include_events: bool = False,
    events_limit: int = 200,
    memory: list[dict[str, Any]] | None = None,
) -> UiTask:
    """Fold Task + its events into a UI-friendly projection.

    Stage keys in `stages` and `current_stage` are aliased via STAGE_ALIAS.
    Aggregates are summed from `stage_finished` events.
    """
    stages: dict[str, UiStage] = {}
    total_cost = 0.0
    tokens_in_total = 0
    tokens_out_total = 0
    duration_ms_total = 0
    running_started_ts_ms: dict[str, int] = {}

    for ev in events:
        aliased = alias_stage(ev.stage)
        payload = ev.payload or {}

        if ev.kind == "stage_started":
            stages[aliased] = UiStage(
                name=aliased,
                status="running",
                agent=payload.get("agent"),
                input=payload.get("input"),
            )
            running_started_ts_ms[aliased] = ev.ts_ms
        elif ev.kind == "stage_finished":
            st = stages.get(aliased) or UiStage(name=aliased, status="running")
            st.status = "done"
            st.duration_ms = payload.get("duration_ms")
            st.cost_usd = payload.get("cost_usd")
            st.tokens_in = payload.get("tokens_in")
            st.tokens_out = payload.get("tokens_out")
            if "output" in payload:
                st.output = payload.get("output")
            stages[aliased] = st

            if isinstance(st.cost_usd, (int, float)):
                total_cost += float(st.cost_usd)
            if isinstance(st.tokens_in, int):
                tokens_in_total += st.tokens_in
            if isinstance(st.tokens_out, int):
                tokens_out_total += st.tokens_out
            if isinstance(st.duration_ms, int):
                duration_ms_total += st.duration_ms
            running_started_ts_ms.pop(aliased, None)
        elif ev.kind == "stage_failed":
            st = stages.get(aliased) or UiStage(name=aliased, status="running")
            st.status = "failed"
            st.error = payload.get("error")
            if "duration_ms" in payload:
                st.duration_ms = payload.get("duration_ms")
            stages[aliased] = st
            running_started_ts_ms.pop(aliased, None)

    if running_started_ts_ms:
        now_ms = int(time.time() * 1000)
        for aliased, started in running_started_ts_ms.items():
            elapsed = max(0, now_ms - started)
            duration_ms_total += elapsed
            st = stages.get(aliased)
            if st is not None:
                st.duration_ms = elapsed

    ui_events: list[UiEvent] | None = None
    if include_events:
        tail = events[-events_limit:] if events_limit > 0 else events
        ui_events = [
            UiEvent(
                seq=ev.seq,
                stage=alias_stage(ev.stage),
                kind=ev.kind,
                ts_ms=ev.ts_ms,
                payload=ev.payload or {},
            )
            for ev in tail
        ]

    return UiTask(
        id=task.id or 0,
        repo=task.repo,
        issue_number=task.issue_number,
        issue_title=task.issue_title,
        status=task.status.value,
        current_stage=alias_stage(task.current_stage.value),
        attempts=task.attempts,
        pr_url=task.pr_url,
        branch_name=task.branch_name,
        worktree_path=task.worktree_path,
        updated_at=task.updated_at,
        created_at=task.created_at,
        total_cost_usd=round(total_cost, 6),
        tokens_in_total=tokens_in_total,
        tokens_out_total=tokens_out_total,
        duration_ms_total=duration_ms_total,
        stages=stages,
        memory=[UiMemoryEntry(**entry) for entry in (memory or [])],
        events=ui_events,
    )
