from __future__ import annotations

import json
from pathlib import Path

from foundry.mcp.config import (
    build_mcp_config,
    mcp_config_path_for_run,
    write_mcp_config,
)


def test_build_mcp_config_packs_required_env(tmp_path: Path) -> None:
    cfg = build_mcp_config(
        db_path=tmp_path / "f.sqlite",
        run_id=7,
        automation_id="dev_task",
    )

    server = cfg["mcpServers"]["foundry"]
    assert server["command"] == "uv"
    assert server["args"] == ["run", "python", "-m", "foundry.mcp.server"]
    env = server["env"]
    assert env["FOUNDRY_DB_PATH"] == str(tmp_path / "f.sqlite")
    assert env["FOUNDRY_RUN_ID"] == "7"
    assert env["FOUNDRY_AUTOMATION_ID"] == "dev_task"
    # No skill whitelist anymore — server registers everything in SKILL_REGISTRY.
    assert "FOUNDRY_ENABLED_SKILLS" not in env
    assert "FOUNDRY_PARENT_EVENT_SEQ" not in env


def test_build_mcp_config_includes_parent_event_seq_when_set(tmp_path: Path) -> None:
    cfg = build_mcp_config(
        db_path=tmp_path / "f.sqlite",
        run_id=1,
        automation_id="a",
        parent_event_seq=12,
    )

    assert cfg["mcpServers"]["foundry"]["env"]["FOUNDRY_PARENT_EVENT_SEQ"] == "12"


def test_build_mcp_config_merges_extra_env(tmp_path: Path) -> None:
    cfg = build_mcp_config(
        db_path=tmp_path / "f.sqlite",
        run_id=1,
        automation_id="a",
        extra_env={"FOUNDRY_WORKTREE": "/tmp/wt", "FOUNDRY_BRANCH": "br"},
    )

    env = cfg["mcpServers"]["foundry"]["env"]
    assert env["FOUNDRY_WORKTREE"] == "/tmp/wt"
    assert env["FOUNDRY_BRANCH"] == "br"


def test_write_mcp_config_round_trips(tmp_path: Path) -> None:
    cfg = build_mcp_config(
        db_path=tmp_path / "f.sqlite",
        run_id=1,
        automation_id="a",
    )
    out = mcp_config_path_for_run(tmp_path, 1)

    write_mcp_config(out, cfg)

    assert out.exists()
    assert json.loads(out.read_text()) == cfg
    assert out.name == "run-1-mcp.json"
