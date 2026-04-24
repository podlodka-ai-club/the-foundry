from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from foundry.agents import AgentSettings, AgentStage, AgentTask
from foundry.agents.codex_cli import CodexCliAgent


def _task(task_id: int = 1) -> AgentTask:
    return AgentTask(id=task_id, title="t", description="d")


def _settings(**overrides: object) -> AgentSettings:
    defaults: dict = {
        "stage": AgentStage.IMPLEMENT,
        "backend": "codex_cli",
        "timeout_sec": 60,
        "max_turns": 3,
        "model": "gpt-5",
    }
    defaults.update(overrides)
    return AgentSettings(**defaults)  # type: ignore[arg-type]


def test_extract_session_id_from_thread_started() -> None:
    events = [
        {"type": "thread.started", "thread_id": "019dbdb2-3348-7043"},
        {"type": "turn.started"},
    ]

    assert CodexCliAgent._extract_session_id(events) == "019dbdb2-3348-7043"


def test_extract_session_id_returns_none_when_missing() -> None:
    assert CodexCliAgent._extract_session_id([{"type": "turn.started"}]) is None


def test_extract_final_text_returns_last_agent_message() -> None:
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "first"}},
        {"type": "item.completed", "item": {"type": "tool_call", "name": "fs_read"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "second"}},
    ]

    assert CodexCliAgent._extract_final_text(events) == "second"


def test_extract_final_text_skips_non_agent_items() -> None:
    events = [{"type": "item.completed", "item": {"type": "tool_call"}}]

    assert CodexCliAgent._extract_final_text(events) == ""


def test_apply_uses_exec_for_fresh_and_resume_subcommand_next(tmp_path: Path) -> None:
    agent = CodexCliAgent(settings=_settings())
    task = _task(task_id=9)
    fresh_events = [
        {"type": "thread.started", "thread_id": "tid-9"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
    ]
    resume_events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "again"}},
    ]

    with patch("foundry.agents.codex_cli.run_cli_jsonl") as run:
        run.side_effect = [fresh_events, resume_events]
        first = agent.apply(task=task, worktree=tmp_path, input="hi")
        second = agent.apply(task=task, worktree=tmp_path, input="hi again")

    assert first.response == "done"
    assert second.response == "again"
    assert agent.get_session_id(task) == "tid-9"
    fresh_cmd = run.call_args_list[0].args[0]
    resume_cmd = run.call_args_list[1].args[0]
    assert fresh_cmd[:2] == ["codex", "exec"]
    assert "resume" not in fresh_cmd
    assert resume_cmd[:3] == ["codex", "exec", "resume"]
    assert "tid-9" in resume_cmd


def test_apply_passes_model_and_worktree_to_cli(tmp_path: Path) -> None:
    agent = CodexCliAgent(settings=_settings(model="gpt-4o"))

    with patch(
        "foundry.agents.codex_cli.run_cli_jsonl",
        return_value=[{"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}],
    ) as run:
        agent.apply(task=_task(), worktree=tmp_path, input="")

    cmd = run.call_args.args[0]
    assert cmd[cmd.index("-m") + 1] == "gpt-4o"
    assert cmd[cmd.index("-C") + 1] == str(tmp_path)
    assert "--full-auto" in cmd
    assert "--skip-git-repo-check" in cmd
    assert run.call_args.kwargs["cwd"] == tmp_path


def test_extract_usage_from_turn_completed() -> None:
    events = [
        {"type": "thread.started", "thread_id": "t"},
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 300,
                "output_tokens": 80,
                "cached_input_tokens": 120,
            },
        },
    ]

    got = CodexCliAgent._extract_usage(events)

    assert got == {"input": 300, "output": 80, "cache_read_input": 120}


def test_extract_usage_sums_multiple_turns() -> None:
    events = [
        {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}},
        {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 50}},
    ]

    got = CodexCliAgent._extract_usage(events)

    assert got == {"input": 110, "output": 55}


def test_extract_usage_returns_none_when_no_turn_completed() -> None:
    events = [{"type": "item.completed", "item": {"type": "agent_message", "text": "x"}}]

    assert CodexCliAgent._extract_usage(events) is None
