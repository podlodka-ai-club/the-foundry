from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from foundry.agents import AgentSettings, AgentStage, AgentTask
from foundry.agents.codex_cli import CodexCliAgent
from foundry.agents.streaming import CliProcessError
from foundry.events import read_events
from foundry.state import init_db


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

    with patch("foundry.agents.codex_cli.iter_cli_jsonl_with_retry") as run:
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
        "foundry.agents.codex_cli.iter_cli_jsonl_with_retry",
        return_value=[{"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}],
    ) as run:
        agent.apply(task=_task(), worktree=tmp_path, input="")

    cmd = run.call_args.args[0]
    assert cmd[cmd.index("-m") + 1] == "gpt-4o"
    assert cmd[cmd.index("-C") + 1] == str(tmp_path)
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
    assert "--skip-git-repo-check" in cmd
    assert run.call_args.kwargs["cwd"] == tmp_path
    assert run.call_args.kwargs["env"] is not None


def test_apply_can_opt_into_unsafe_codex_flag(tmp_path: Path) -> None:
    agent = CodexCliAgent(settings=_settings(safe_agent_mode=False))

    with patch(
        "foundry.agents.codex_cli.iter_cli_jsonl_with_retry",
        return_value=[{"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}],
    ) as run:
        agent.apply(task=_task(), worktree=tmp_path, input="")

    assert "--dangerously-bypass-approvals-and-sandbox" in run.call_args.args[0]


def test_apply_passes_configured_codex_sandbox_mode(tmp_path: Path) -> None:
    agent = CodexCliAgent(settings=_settings(sandbox_mode="danger-full-access"))

    with patch(
        "foundry.agents.codex_cli.iter_cli_jsonl_with_retry",
        return_value=[{"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}],
    ) as run:
        agent.apply(task=_task(), worktree=tmp_path, input="")

    cmd = run.call_args.args[0]
    assert cmd[cmd.index("--sandbox") + 1] == "danger-full-access"
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd


def test_apply_propagates_cli_process_failures(tmp_path: Path) -> None:
    agent = CodexCliAgent(settings=_settings())

    with patch(
        "foundry.agents.codex_cli.iter_cli_jsonl_with_retry",
        side_effect=CliProcessError(["codex"], 1, "bwrap: No permissions to create a new namespace"),
    ):
        try:
            agent.apply(task=_task(), worktree=tmp_path, input="")
        except CliProcessError as exc:
            assert "bwrap" in str(exc)
        else:
            raise AssertionError("expected CliProcessError")


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


def test_codex_tool_item_normalizes_json_arguments_and_shell_name() -> None:
    raw = CodexCliAgent._codex_tool_item_to_raw(
        {
            "type": "local_shell_call",
            "arguments": '{"command": "pytest -q", "description": "run tests"}',
        }
    )

    assert raw == {
        "name": "Bash",
        "input": {"command": "pytest -q", "description": "run tests"},
    }


def test_codex_cli_emits_agent_events_during_apply(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    agent = CodexCliAgent(settings=_settings(db_path=db))
    task = _task(task_id=202)
    streamed = [
        {"type": "thread.started", "thread_id": "tid-202"},
        {
            "type": "item.completed",
            "item": {
                "type": "tool_call",
                "name": "Read",
                "input": {"file_path": "/repo/app.py"},
            },
        },
        {
            "type": "item.completed",
            "item": {"type": "reasoning", "summary": "Need to inspect the failing UI path."},
        },
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "fixed\nmore"},
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    ]

    with patch(
        "foundry.agents.codex_cli.iter_cli_jsonl_with_retry",
        return_value=streamed,
    ):
        result = agent.apply(task=task, worktree=tmp_path, input="")

    assert result.response == "fixed\nmore"
    assert result.result == "fixed"
    assert result.tokens_in == 10
    assert result.tokens_out == 5

    events = read_events(db, task_id=202)
    kinds = [(e.kind, e.seq) for e in events]
    kind_names = [k for k, _ in kinds]
    assert "agent_tool" in kind_names
    assert "agent_thinking" in kind_names
    assert "agent_text" in kind_names
    assert "agent_result" in kind_names

    tool_event = next(e for e in events if e.kind == "agent_tool")
    assert tool_event.payload["tool"] == "Read"
    assert tool_event.payload["detail"] == "/repo/app.py"

    tool_seq = next(seq for k, seq in kinds if k == "agent_tool")
    result_seq = next(seq for k, seq in kinds if k == "agent_result")
    assert tool_seq < result_seq

    result_event = next(e for e in events if e.kind == "agent_result")
    assert result_event.payload["summary"] == "fixed"
    assert result_event.payload["text"] == "fixed\nmore"
