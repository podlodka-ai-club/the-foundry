from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    DONE = "done"
    FAILED = "failed"
    UNCLEAR = "unclear"


class FailureKind(str, Enum):
    DETERMINISTIC = "deterministic"
    ACCEPTANCE = "acceptance"
    INFRA = "infra"
    UNCLEAR = "unclear"
    DANGEROUS = "dangerous"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Event:
    """Top-level trigger event emitted by a listener.

    `external_id` is unique within `source` (enforced via UNIQUE constraint
    in `events` table) — re-emits from the same channel are deduped at the
    DB layer.
    """

    id: int
    source: str
    external_id: str
    kind: str
    payload: dict[str, Any]
    created_at: str
    parent_event_id: int | None = None


@dataclass
class RunEvent:
    """Per-run breadcrumb appended to `run_events` (was `task_events`).

    `seq` is monotonic per `run_id` (UNIQUE(run_id, seq)). `parent_event_seq`
    points to the parent breadcrumb in the same run when the entry belongs
    to a sub-agent call, or stays None for top-level entries.
    """

    id: int
    run_id: int
    seq: int
    stage: str
    kind: str
    ts_ms: int
    payload: dict[str, Any]
    parent_event_seq: int | None = None


@dataclass
class Run:
    id: int | None
    automation_id: str
    event_id: int
    session_id: str
    session_seq: int = 1
    status: RunStatus = RunStatus.RUNNING
    started_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    duration_sec: float | None = None
    cost_usd: float | None = None
    failure_kind: FailureKind | None = None
    failure_msg: str | None = None
    waiting_reason: str | None = None
    outcome: str | None = None
    agent_session_id: str | None = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
