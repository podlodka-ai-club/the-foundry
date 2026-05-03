from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_mcp_config(
    *,
    db_path: Path,
    run_id: int,
    automation_id: str,
    parent_event_seq: int | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compose the per-run MCP server config (mcpServers wire format).

    No skill whitelist anymore — the server registers everything in
    `foundry.skills.SKILL_REGISTRY` plus the always-available control-plane
    tools. Per-automation gating moves into prompts and (later) per-folder
    slash-commands.
    """
    env: dict[str, str] = {
        "FOUNDRY_DB_PATH": str(db_path),
        "FOUNDRY_RUN_ID": str(run_id),
        "FOUNDRY_AUTOMATION_ID": automation_id,
    }
    if parent_event_seq is not None:
        env["FOUNDRY_PARENT_EVENT_SEQ"] = str(parent_event_seq)
    if extra_env:
        env.update(extra_env)
    return {
        "mcpServers": {
            "foundry": {
                "command": "uv",
                "args": ["run", "python", "-m", "foundry.mcp.server"],
                "env": env,
            }
        }
    }


def write_mcp_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def mcp_config_path_for_run(worktree_root: Path, run_id: int) -> Path:
    return worktree_root / f"run-{run_id}-mcp.json"
