from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from foundry.agents.base import AgentTask
from foundry.agents.config import AgentSettings
from foundry.agents.context import agent_event_context
from foundry.agents.factory import make_agent
from foundry.events import record_event
from foundry.session import compute_session_id
from foundry.subagents import get_subagent


def run_subagent(*, name: str, prompt: str, caller_id: str) -> dict[str, Any]:
    """Invoke a registered sub-agent. Reads run context from env.

    Writes paired `agent_call_started` / `agent_call_finished` (or
    `agent_call_failed`) framing events under stage `subagent:<name>` into
    `run_events`, with the inner agent's events nested under the started-seq
    via `parent_event_seq` (propagated through `agent_event_context`).

    Note on `compute_session_id` signature `(external_id, automation_id,
    agent_type)` — here we role-alias `caller_id → external_id`,
    `sub.name → automation_id`, `sub.backend → agent_type`. The legacy
    parameter names were settled in C1 (see `tests/test_session.py`) and
    are intentionally not changed.
    """
    db_path = Path(os.environ["FOUNDRY_DB_PATH"])
    run_id = int(os.environ["FOUNDRY_RUN_ID"])
    raw_parent = os.environ.get("FOUNDRY_PARENT_EVENT_SEQ")
    parent_event_seq = int(raw_parent) if raw_parent else None
    worktree = Path(os.environ.get("FOUNDRY_WORKTREE", os.getcwd()))

    sub = get_subagent(name)
    if sub is None:
        return {"ok": False, "error": f"sub-agent not registered: {name}"}

    sub_session_id = compute_session_id(caller_id, sub.name, sub.backend)

    started_seq = record_event(
        db_path,
        run_id=run_id,
        stage=f"subagent:{name}",
        kind="agent_call_started",
        payload={
            "subagent": name,
            "backend": sub.backend,
            "sub_session_id": sub_session_id,
            "caller_id": caller_id,
            "prompt_preview": prompt[:200],
        },
        parent_event_seq=parent_event_seq,
    )

    settings = AgentSettings(
        backend=sub.backend,
        model=sub.model or "haiku",
        db_path=db_path,
    )
    agent = make_agent(settings)
    task = AgentTask(id=run_id, title=f"subagent:{name}", description=prompt)

    t0 = time.monotonic()
    response_text = ""
    cost_usd: float | None = None
    error: str | None = None

    try:
        with agent_event_context(parent_event_seq=started_seq):
            result = agent.apply(task=task, worktree=worktree, input=prompt)
        response_text = getattr(result, "response", str(result))
        cost_usd = getattr(result, "cost_usd", None)
    except Exception as exc:  # noqa: BLE001 — surface anything as run-event
        error = repr(exc)

    duration_sec = time.monotonic() - t0

    finish_payload: dict[str, Any] = {
        "subagent": name,
        "sub_session_id": sub_session_id,
        "response_preview": response_text[:200],
        "duration_sec": duration_sec,
        "cost_usd": cost_usd,
    }
    if error is not None:
        finish_payload["error"] = error

    record_event(
        db_path,
        run_id=run_id,
        stage=f"subagent:{name}",
        kind="agent_call_finished" if error is None else "agent_call_failed",
        payload=finish_payload,
        parent_event_seq=parent_event_seq,
    )

    if error is not None:
        return {"ok": False, "error": error, "sub_session_id": sub_session_id}
    return {
        "ok": True,
        "response": response_text,
        "cost_usd": cost_usd,
        "duration_sec": duration_sec,
        "sub_session_id": sub_session_id,
    }
