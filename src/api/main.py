"""FastAPI app for the C6 web UI.

Endpoints are read-mostly with three POST stubs (`messages`, `stop`, `retry`).
The single source of truth is SQLite (`runs`, `run_events`, `events`); the
orchestrator writes from a separate process so the API only reads. SSE is
implemented by polling SQLite via `bus.subscribe(...)`.

Settings come from `foundry.config.load_settings()` lazily through the
`get_db_path` dependency so tests can override it without touching env vars.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from foundry import state
from foundry.automations.registry import AUTOMATIONS, get_automation
from foundry.config import ConfigError, load_settings
from foundry.events import read_events, record_event
from foundry.listeners._factory import build_listeners
from foundry.listeners.cron_rules import DEFAULT_CRON_RULES
from foundry.models import Event, FailureKind, Run, RunEvent, RunStatus

from . import bus
from .models import (
    PostMessageBody,
    UiAutomation,
    UiAutomationCounts,
    UiEvent,
    UiRun,
    UiRunDetail,
    UiRunTrigger,
    UiTrigger,
)

app = FastAPI(title="The Foundry API")


# --- DB path dependency -----------------------------------------------------


def _resolve_db_path() -> Path:
    """Lazy-resolve DB path from settings, with env override for tests."""
    override = os.environ.get("FOUNDRY_DB_PATH_OVERRIDE", "").strip()
    if override:
        return Path(override)
    try:
        return load_settings().db_path
    except ConfigError:
        # Allow API to boot for `/` health check even without env file.
        return Path("./data/foundry.sqlite").resolve()


def get_db_path() -> Path:
    return _resolve_db_path()


# --- Helpers ----------------------------------------------------------------


_HEALTH_THRESHOLD_SEC = 300
_KIND_FOR_SOURCE = {
    "github_issues": "github",
    "cron": "cron",
    "discord": "discord",
}


def _kind_for_source(source: str) -> str:
    return _KIND_FOR_SOURCE.get(source, source)


def _parse_iso(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _health(last_seen: str | None, *, threshold_sec: int = _HEALTH_THRESHOLD_SEC) -> str | None:
    if last_seen is None:
        return None
    dt = _parse_iso(last_seen)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = (now - dt).total_seconds()
    return "ok" if delta < threshold_sec else "stale"


def _trigger_for_event(event: Event | None) -> UiRunTrigger | None:
    if event is None:
        return None
    payload = event.payload or {}
    source = event.source
    if source == "github_issues":
        text = str(payload.get("title", ""))
        author = payload.get("author") or payload.get("user") or None
    elif source == "cron":
        tick_at = payload.get("tick_at") or payload.get("tick") or ""
        text = f"cron tick @ {tick_at}"
        author = None
    elif source == "discord":
        text = str(payload.get("content", ""))
        author = payload.get("author") or None
    else:
        text = str(payload.get("text") or payload.get("title") or "")
        author = payload.get("author")
    return UiRunTrigger(
        source=source,
        external_id=event.external_id,
        text=text,
        author=author if isinstance(author, str) else None,
        kind=event.kind,
    )


def _run_to_ui(run: Run, event: Event | None) -> UiRun:
    return UiRun(
        id=run.id or 0,
        automation_id=run.automation_id,
        event_id=run.event_id,
        session_id=run.session_id,
        session_seq=run.session_seq,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_sec=run.duration_sec,
        cost_usd=run.cost_usd,
        failure_kind=run.failure_kind.value if run.failure_kind else None,
        failure_msg=run.failure_msg,
        waiting_reason=run.waiting_reason,
        agent_session_id=run.agent_session_id,
        trigger=_trigger_for_event(event),
    )


def _run_event_to_ui(ev: RunEvent) -> UiEvent:
    return UiEvent(
        seq=ev.seq,
        run_id=ev.run_id,
        stage=ev.stage,
        kind=ev.kind,
        ts_ms=ev.ts_ms,
        payload=ev.payload,
        parent_event_seq=ev.parent_event_seq,
    )


def _resolve_event(db_path: Path, event_id: int) -> Event | None:
    return state.get_event(db_path, event_id)


def _expand_run_filter(filter_: str | None) -> list[RunStatus] | None:
    if filter_ is None:
        return None
    if filter_ == "running":
        return [RunStatus.RUNNING]
    if filter_ == "waiting":
        return [RunStatus.WAITING]
    if filter_ == "failed":
        return [RunStatus.FAILED, RunStatus.UNCLEAR]
    if filter_ == "pending":
        return [RunStatus.PENDING]
    if filter_ == "done":
        return [RunStatus.DONE]
    raise HTTPException(status_code=400, detail=f"unknown filter: {filter_!r}")


# --- Health -----------------------------------------------------------------


@app.get("/")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


# --- Automations ------------------------------------------------------------


@app.get("/api/automations", response_model=list[UiAutomation])
async def get_automations(db_path: Path = Depends(get_db_path)) -> list[UiAutomation]:
    counts = state.count_runs_by_automation_status(db_path) if db_path.exists() else {}
    out: list[UiAutomation] = []
    for a in AUTOMATIONS:
        running = counts.get((a.id, RunStatus.RUNNING.value), 0)
        waiting = counts.get((a.id, RunStatus.WAITING.value), 0)
        pending = counts.get((a.id, RunStatus.PENDING.value), 0)
        total = sum(v for (aid, _st), v in counts.items() if aid == a.id)
        out.append(
            UiAutomation(
                id=a.id,
                name=a.name,
                description=a.description,
                triggers=list(a.triggers),
                skills=list(a.skills),
                agent=dict(a.agent),
                counts=UiAutomationCounts(
                    running=running,
                    waiting=waiting,
                    pending=pending,
                    total=total,
                ),
            )
        )
    return out


# --- Triggers ---------------------------------------------------------------


def _known_trigger_ids() -> list[tuple[str, str]]:
    """Return [(trigger_id, source)] for the listener set we boot."""
    seen: list[tuple[str, str]] = []
    try:
        settings = load_settings()
        listeners = build_listeners(settings)
        for l in listeners:
            seen.append((l.id, l.source))
    except (ConfigError, Exception):
        # Fall back to declared listener ids.
        for src in ("github_issues", "cron", "discord"):
            seen.append((src, src))

    # Add cron rules as separate triggers in addition to the umbrella `cron`.
    for rule in DEFAULT_CRON_RULES:
        seen.append((f"cron:{rule.id}", "cron"))
    # Dedup by id while preserving order.
    seen_ids: set[str] = set()
    unique: list[tuple[str, str]] = []
    for tid, src in seen:
        if tid in seen_ids:
            continue
        seen_ids.add(tid)
        unique.append((tid, src))
    return unique


@app.get("/api/triggers", response_model=list[UiTrigger])
async def get_triggers(db_path: Path = Depends(get_db_path)) -> list[UiTrigger]:
    last_seen_map = (
        state.last_event_at_by_source(db_path) if db_path.exists() else {}
    )
    out: list[UiTrigger] = []
    for tid, source in _known_trigger_ids():
        last = last_seen_map.get(source)
        out.append(
            UiTrigger(
                id=tid,
                source=source,
                kind=_kind_for_source(source),
                last_seen=last,
                health=_health(last),
            )
        )
    return out


# --- Runs -------------------------------------------------------------------


@app.get("/api/runs", response_model=list[UiRun])
async def list_runs_endpoint(
    filter: str | None = None,
    limit: int = 100,
    db_path: Path = Depends(get_db_path),
) -> list[UiRun]:
    statuses = _expand_run_filter(filter)
    if not db_path.exists():
        return []
    if statuses is None:
        runs = state.list_runs(db_path, limit=limit)
    else:
        runs = []
        for st in statuses:
            runs.extend(state.list_runs(db_path, status=st, limit=limit))
        runs.sort(key=lambda r: r.id or 0, reverse=True)
        runs = runs[:limit]
    return [_run_to_ui(r, _resolve_event(db_path, r.event_id)) for r in runs]


@app.get(
    "/api/automations/{automation_id}/runs",
    response_model=list[UiRun],
)
async def list_automation_runs(
    automation_id: str,
    status: str | None = None,
    limit: int = 100,
    db_path: Path = Depends(get_db_path),
) -> list[UiRun]:
    if get_automation(automation_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown automation: {automation_id}")
    if not db_path.exists():
        return []
    status_enum: RunStatus | None = None
    if status is not None:
        try:
            status_enum = RunStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"unknown status: {status!r}")
    runs = state.list_runs(
        db_path, automation_id=automation_id, status=status_enum, limit=limit
    )
    return [_run_to_ui(r, _resolve_event(db_path, r.event_id)) for r in runs]


@app.get("/api/runs/{run_id}", response_model=UiRunDetail)
async def get_run_detail(
    run_id: int, db_path: Path = Depends(get_db_path)
) -> UiRunDetail:
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    run = state.get_run(db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    event = _resolve_event(db_path, run.event_id)
    base = _run_to_ui(run, event)
    events = read_events(db_path, run_id)
    return UiRunDetail(
        **base.model_dump(),
        events=[_run_event_to_ui(ev) for ev in events],
    )


# --- SSE --------------------------------------------------------------------


def _sse_format(ev: UiEvent) -> bytes:
    payload = json.dumps(ev.model_dump(), ensure_ascii=False)
    return f"id: {ev.seq}\nevent: run_event\ndata: {payload}\n\n".encode("utf-8")


@app.get("/api/runs/{run_id}/events")
async def stream_run_events(
    run_id: int,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db_path: Path = Depends(get_db_path),
) -> StreamingResponse:
    after_seq: int | None = None
    if last_event_id is not None:
        try:
            after_seq = int(last_event_id)
        except ValueError:
            after_seq = None

    async def is_disconnected() -> bool:
        return await request.is_disconnected()

    async def gen() -> AsyncIterator[bytes]:
        try:
            async for ev in bus.subscribe(
                db_path,
                run_id=run_id,
                after_seq=after_seq,
                is_disconnected=is_disconnected,
            ):
                yield _sse_format(_run_event_to_ui(ev))
                if await request.is_disconnected():
                    break
        except asyncio.CancelledError:
            return

    return StreamingResponse(gen(), media_type="text/event-stream")


# --- Mutations --------------------------------------------------------------


@app.post("/api/runs/{run_id}/messages", status_code=202)
async def post_run_message(
    run_id: int,
    body: PostMessageBody,
    db_path: Path = Depends(get_db_path),
) -> dict[str, Any]:
    run = state.get_run(db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    seq = record_event(
        db_path,
        run_id,
        "user_input",
        "user_message",
        {"type": body.type, "text": body.text, "ts_ms": int(time.time() * 1000)},
    )
    return {"ok": True, "seq": seq}


_TERMINAL_STATUSES = {RunStatus.DONE, RunStatus.FAILED, RunStatus.UNCLEAR}


@app.post("/api/runs/{run_id}/stop")
async def post_run_stop(
    run_id: int, db_path: Path = Depends(get_db_path)
) -> dict[str, Any]:
    run = state.get_run(db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    if run.status in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"run {run_id} already in terminal status {run.status.value}",
        )
    started = _parse_iso(run.started_at)
    duration = 0.0
    if started is not None:
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        duration = max(
            0.0, (datetime.now(timezone.utc) - started).total_seconds()
        )
    state.finish_run(
        db_path,
        run_id,
        status=RunStatus.FAILED,
        duration_sec=duration,
        failure_kind=FailureKind.INFRA,
        failure_msg="stopped by user",
    )
    record_event(
        db_path,
        run_id,
        "user_input",
        "user_stop",
        {"ts_ms": int(time.time() * 1000)},
    )
    return {"ok": True}


@app.post("/api/runs/{run_id}/retry")
async def post_run_retry(
    run_id: int, db_path: Path = Depends(get_db_path)
) -> dict[str, Any]:
    run = state.get_run(db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    if run.status not in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"run {run_id} is not in a terminal status (status={run.status.value})",
        )
    next_seq = state.next_session_seq(db_path, run.session_id)
    new_run_id = state.create_run(
        db_path,
        automation_id=run.automation_id,
        event_id=run.event_id,
        session_id=run.session_id,
        session_seq=next_seq,
        status=RunStatus.PENDING,
    )
    record_event(
        db_path,
        new_run_id,
        "user_input",
        "user_retry",
        {
            "ts_ms": int(time.time() * 1000),
            "previous_run_id": run_id,
            "session_seq": next_seq,
        },
    )
    return {"ok": True, "run_id": new_run_id}
