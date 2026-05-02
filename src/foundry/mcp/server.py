from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from foundry.events import record_event

mcp = FastMCP("foundry")


def _ctx() -> tuple[Path, int, int | None]:
    """Read the per-run context from env on every tool invocation.

    `FOUNDRY_DB_PATH` and `FOUNDRY_RUN_ID` are required; `FOUNDRY_PARENT_EVENT_SEQ`
    is optional and nests this run's tool-emitted events under a parent
    breadcrumb when set (e.g. when the orchestrator launches the MCP server
    inside an existing stage span).
    """
    db_path = Path(os.environ["FOUNDRY_DB_PATH"])
    run_id = int(os.environ["FOUNDRY_RUN_ID"])
    raw_parent = os.environ.get("FOUNDRY_PARENT_EVENT_SEQ")
    parent = int(raw_parent) if raw_parent else None
    return db_path, run_id, parent


def mark_milestone_impl(label: str) -> dict[str, Any]:
    """Logic for the `mark_milestone` tool, exposed for unit tests."""
    db_path, run_id, parent = _ctx()
    seq = record_event(
        db_path,
        run_id=run_id,
        stage="milestone",
        kind="mark",
        payload={"label": label},
        parent_event_seq=parent,
    )
    return {"ok": True, "seq": seq}


def compact_context_impl() -> dict[str, Any]:
    return {"ok": False, "error": "not implemented yet"}


def call_subagent_impl(name: str, prompt: str, id: str) -> dict[str, Any]:
    # Lazy import — `runner` pulls in agent stack which is heavier than the
    # MCP-server skeleton needs at import time.
    from foundry.mcp.runner import run_subagent

    return run_subagent(name=name, prompt=prompt, caller_id=id)


@mcp.tool()
def mark_milestone(label: str) -> dict[str, Any]:
    """Mark a milestone in the run's event tree."""
    return mark_milestone_impl(label)


@mcp.tool()
def compact_context() -> dict[str, Any]:
    """Reserved for future context compaction; not implemented yet."""
    return compact_context_impl()


@mcp.tool()
def call_subagent(name: str, prompt: str, id: str) -> dict[str, Any]:
    """Recursively invoke a registered sub-agent."""
    return call_subagent_impl(name=name, prompt=prompt, id=id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
