from __future__ import annotations

from collections import Counter

from fastapi import FastAPI, HTTPException

from foundry import state
from foundry.config import ConfigError, load_settings
from foundry.events import read_events
from foundry.models import Stage, TaskStatus

from .projections import UiMemoryEntry, UiTask, project_task
from .sse import router as sse_router

app = FastAPI(title="The Foundry API")
app.include_router(sse_router)


@app.get("/")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


def _settings_or_raise():
    try:
        return load_settings()
    except ConfigError as exc:
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}")


@app.get("/api/tasks", response_model=list[UiTask])
async def get_tasks() -> list[UiTask]:
    """List all tasks with aggregated stage projections (no events)."""
    settings = _settings_or_raise()
    state.init_db(settings.db_path)

    tasks = state.list_tasks(settings.db_path)
    result: list[UiTask] = []
    for task in tasks:
        events = read_events(settings.db_path, task.id) if task.id is not None else []
        memory = state.list_repo_memory(settings.db_path, task.repo)
        result.append(project_task(task, events, include_events=False, memory=memory))
    return result


@app.get("/api/tasks/{task_id}", response_model=UiTask)
async def get_task(task_id: int) -> UiTask:
    """Full task projection including the last 200 events."""
    settings = _settings_or_raise()
    state.init_db(settings.db_path)

    task = state.get_task(settings.db_path, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    events = read_events(settings.db_path, task_id)
    memory = state.list_repo_memory(settings.db_path, task.repo)
    return project_task(
        task, events, include_events=True, events_limit=200, memory=memory
    )


@app.post("/api/tasks/{task_id}/reset", response_model=UiTask)
async def reset_task(task_id: int) -> UiTask:
    """Reset a task to pending/fetch so the worker can retry it."""
    return _reset_task(task_id)


@app.post("/api/tasks/{task_id}/resume", response_model=UiTask)
async def resume_task(task_id: int) -> UiTask:
    """Resume a human-blocked task after someone answered in the issue."""
    return _reset_task(task_id)


def _reset_task(task_id: int) -> UiTask:
    settings = _settings_or_raise()
    state.init_db(settings.db_path)

    task = state.get_task(settings.db_path, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if task.status == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Running tasks cannot be reset")

    task.status = TaskStatus.PENDING
    task.current_stage = Stage.FETCH
    task.pr_url = None
    task = state.upsert_task(settings.db_path, task)

    events = read_events(settings.db_path, task_id)
    memory = state.list_repo_memory(settings.db_path, task.repo)
    return project_task(
        task, events, include_events=True, events_limit=200, memory=memory
    )


@app.get("/api/repos")
async def get_repos() -> list[dict]:
    """Aggregate task counts per repo, grouped by status."""
    settings = _settings_or_raise()
    state.init_db(settings.db_path)

    tasks = state.list_tasks(settings.db_path)
    per_repo: dict[str, Counter[str]] = {}
    for task in tasks:
        per_repo.setdefault(task.repo, Counter())[task.status.value.upper()] += 1

    out: list[dict] = []
    for repo in sorted(per_repo.keys()):
        counts = per_repo[repo]
        out.append(
            {
                "repo": repo,
                "counts": {
                    "RUNNING": counts.get("RUNNING", 0),
                    "BLOCKED": counts.get("BLOCKED", 0),
                    "DONE": counts.get("DONE", 0),
                    "FAILED": counts.get("FAILED", 0),
                    "PENDING": counts.get("PENDING", 0),
                },
            }
        )
    return out


@app.get("/api/repos/{repo:path}/memory", response_model=list[UiMemoryEntry])
async def get_repo_memory(repo: str) -> list[UiMemoryEntry]:
    """List repo-level memory entries."""
    settings = _settings_or_raise()
    state.init_db(settings.db_path)

    entries = state.list_repo_memory(settings.db_path, repo)
    return [UiMemoryEntry(**entry) for entry in entries]
