from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any, Callable

from fastmcp import FastMCP

from foundry.events import record_event
from foundry.skills import SKILL_REGISTRY

mcp = FastMCP("foundry")

_REGISTERED: set[str] = set()


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


def _enabled_skills() -> set[str]:
    raw = os.environ.get("FOUNDRY_ENABLED_SKILLS", "")
    return {s.strip() for s in raw.split(",") if s.strip()}


def _make_skill_wrapper(skill_id: str, impl: Callable[..., dict[str, Any]]):
    @functools.wraps(impl)
    def wrapper(**kwargs: Any) -> dict[str, Any]:
        return impl(**kwargs)
    # FastMCP reads the wrapper's docstring for the tool description; if the
    # underlying skill has no docstring, fall back to a generic line so the
    # tool is well-formed.
    if not wrapper.__doc__:
        wrapper.__doc__ = f"Foundry skill: {skill_id}"
    return wrapper


def _register_enabled_skills() -> None:
    """Register skills listed in FOUNDRY_ENABLED_SKILLS as MCP tools.

    Skills not in the env list stay disabled. Re-entrant safe via
    `_REGISTERED` guard — calling twice is a no-op.
    """
    enabled = _enabled_skills()
    for skill_id, impl in SKILL_REGISTRY.items():
        if skill_id not in enabled or skill_id in _REGISTERED:
            continue
        wrapper = _make_skill_wrapper(skill_id, impl)
        mcp.tool(name=skill_id)(wrapper)
        _REGISTERED.add(skill_id)


_register_enabled_skills()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
