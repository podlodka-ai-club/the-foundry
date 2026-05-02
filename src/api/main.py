from __future__ import annotations

from fastapi import FastAPI, HTTPException

app = FastAPI(title="The Foundry API")


@app.get("/")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


# --- Deprecated /api/tasks/* endpoints --------------------------------------
# Kept as stubs after the C5 legacy purge. Real /api/runs/* surface lands in
# C6; until then these return empty/404 so the existing UI does not crash.


@app.get("/api/tasks")
async def get_tasks() -> list[dict]:
    """Deprecated since C5; awaiting C6."""
    return []


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: int) -> dict:
    raise HTTPException(status_code=404, detail="Deprecated since C5; awaiting C6")


@app.get("/api/repos")
async def get_repos() -> list[dict]:
    """Deprecated since C5; awaiting C6."""
    return []
