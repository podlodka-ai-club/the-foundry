from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Stage(str, Enum):
    FETCH = "fetch"
    CONTEXT = "context"
    PLAN = "plan"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    PR = "pr"
    DONE = "done"
    FAILED = "failed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Task:
    repo: str
    issue_number: int
    issue_title: str
    issue_body: str
    id: int | None = None
    status: TaskStatus = TaskStatus.PENDING
    current_stage: Stage = Stage.FETCH
    attempts: int = 0
    worktree_path: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    logs_json: str = "[]"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
