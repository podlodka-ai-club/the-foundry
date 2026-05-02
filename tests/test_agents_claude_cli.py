from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from foundry.agents import AgentSettings, AgentStage, AgentTask
from foundry.agents.claude_cli import ClaudeCliAgent
from foundry.agents.context import agent_event_context
from foundry.events import read_events
from foundry.state import init_db


def _task(task_id: int = 1) -> AgentTask:
    return AgentTask(id=task_id, title="t", description="d")


def _settings(stage: AgentStage = AgentStage.IMPLEMENT, **overrides: object) -> AgentSettings:
    defaults: dict = {
        "stage": stage,
        "backend": "claude_cli",
        "timeout_sec": 60,
        "max_turns": 3,
        "model": "haiku",
    }
    defaults.update(overrides)
    return AgentSettings(**defaults)  # type: ignore[arg-type]


def test_extract_session_id_picks_first_system_event() -> None:
    events = [
        {"type": "assistant", "message": {}},
        {"type": "system", "session_id": "sess-xyz"},
        {"type": "system", "session_id": "sess-other"},
    ]

    got = ClaudeCliAgent._extract_session_id(events)

    assert got == "sess-xyz"


def test_extract_session_id_returns_none_when_missing() -> None:
    events = [{"type": "assistant"}, {"type": "result", "result": "ok"}]

    assert ClaudeCliAgent._extract_session_id(events) is None


def test_extract_final_text_prefers_result_event() -> None:
    events = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "mid"}]}},
        {"type": "result", "result": "final answer"},
    ]

    assert ClaudeCliAgent._extract_final_text(events) == "final answer"


def test_extract_final_text_falls_back_to_last_assistant_text() -> None:
    events = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "first"}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "second"}]}},
    ]

    assert ClaudeCliAgent._extract_final_text(events) == "second"


def test_extract_final_text_returns_empty_when_no_events() -> None:
    assert ClaudeCliAgent._extract_final_text([]) == ""


def test_apply_caches_session_id_and_resumes_next_call(tmp_path: Path) -> None:
    agent = ClaudeCliAgent(settings=_settings())
    task = _task(task_id=42)
    fresh_events = [
        {"type": "system", "session_id": "sess-42"},
        {"type": "result", "result": "done"},
    ]
    resume_events = [{"type": "result", "result": "followup"}]

    with patch("foundry.agents.claude_cli.iter_cli_jsonl") as run:
        run.side_effect = [iter(fresh_events), iter(resume_events)]

        first = agent.apply(task=task, worktree=tmp_path, input="initial")
        second = agent.apply(task=task, worktree=tmp_path, input="more")

    assert first.response == "done"
    assert second.response == "followup"
    assert agent.get_session_id(task) == "sess-42"
    fresh_cmd = run.call_args_list[0].args[0]
    resume_cmd = run.call_args_list[1].args[0]
    assert "--resume" not in fresh_cmd
    assert "--resume" in resume_cmd
    assert resume_cmd[resume_cmd.index("--resume") + 1] == "sess-42"


def test_apply_passes_model_and_max_turns_to_cli(tmp_path: Path) -> None:
    agent = ClaudeCliAgent(settings=_settings(model="opus", max_turns=11))

    with patch(
        "foundry.agents.claude_cli.iter_cli_jsonl",
        return_value=iter([{"type": "result", "result": "ok"}]),
    ) as run:
        agent.apply(task=_task(), worktree=tmp_path, input="")

    cmd = run.call_args.args[0]
    assert cmd[cmd.index("--model") + 1] == "opus"
    assert cmd[cmd.index("--max-turns") + 1] == "11"
    assert "--dangerously-skip-permissions" in cmd


def test_apply_passes_mcp_config_when_set(tmp_path: Path) -> None:
    cfg = Path("/tmp/foundry-mcp.json")
    agent = ClaudeCliAgent(settings=_settings(mcp_config=cfg))

    with patch(
        "foundry.agents.claude_cli.iter_cli_jsonl",
        return_value=iter([{"type": "result", "result": "ok"}]),
    ) as run:
        agent.apply(task=_task(), worktree=tmp_path, input="")

    cmd = run.call_args.args[0]
    assert "--mcp-config" in cmd
    assert cmd[cmd.index("--mcp-config") + 1] == str(cfg)


def test_apply_omits_mcp_config_when_unset(tmp_path: Path) -> None:
    agent = ClaudeCliAgent(settings=_settings())

    with patch(
        "foundry.agents.claude_cli.iter_cli_jsonl",
        return_value=iter([{"type": "result", "result": "ok"}]),
    ) as run:
        agent.apply(task=_task(), worktree=tmp_path, input="")

    cmd = run.call_args.args[0]
    assert "--mcp-config" not in cmd


def test_apply_runs_in_worktree_cwd(tmp_path: Path) -> None:
    agent = ClaudeCliAgent(settings=_settings())

    with patch(
        "foundry.agents.claude_cli.iter_cli_jsonl",
        return_value=iter([{"type": "result", "result": "ok"}]),
    ) as run:
        agent.apply(task=_task(), worktree=tmp_path, input="")

    assert run.call_args.kwargs["cwd"] == tmp_path


def test_extract_usage_maps_all_token_fields() -> None:
    events = [
        {"type": "system", "session_id": "s"},
        {
            "type": "result",
            "result": "ok",
            "usage": {
                "input_tokens": 120,
                "output_tokens": 45,
                "cache_read_input_tokens": 800,
                "cache_creation_input_tokens": 30,
            },
        },
    ]

    got = ClaudeCliAgent._extract_usage(events)

    assert got == {
        "input": 120,
        "output": 45,
        "cache_read_input": 800,
        "cache_creation_input": 30,
    }


def test_extract_usage_returns_none_when_missing() -> None:
    events = [{"type": "result", "result": "ok"}]

    assert ClaudeCliAgent._extract_usage(events) is None


def test_extract_cost_usd_pulls_total_cost_from_result_event() -> None:
    events = [
        {"type": "system", "session_id": "s"},
        {"type": "result", "result": "ok", "total_cost_usd": 0.1234},
    ]

    assert ClaudeCliAgent._extract_cost_usd(events) == 0.1234


def test_extract_cost_usd_returns_none_when_missing() -> None:
    events = [{"type": "result", "result": "ok"}]

    assert ClaudeCliAgent._extract_cost_usd(events) is None


def test_apply_populates_cost_and_tokens_from_result_event(tmp_path: Path) -> None:
    agent = ClaudeCliAgent(settings=_settings())
    streamed = [
        {"type": "system", "session_id": "s"},
        {
            "type": "result",
            "result": "ok",
            "total_cost_usd": 0.042,
            "usage": {"input_tokens": 200, "output_tokens": 75},
        },
    ]

    with patch(
        "foundry.agents.claude_cli.iter_cli_jsonl",
        return_value=iter(streamed),
    ):
        out = agent.apply(task=_task(), worktree=tmp_path, input="")

    assert out.cost_usd == 0.042
    assert out.tokens_in == 200
    assert out.tokens_out == 75


def test_extract_model_from_modelUsage_keys() -> None:
    events = [
        {"type": "system", "session_id": "s"},
        {
            "type": "result",
            "result": "ok",
            "modelUsage": {
                "claude-haiku-4-5-20251001": {"inputTokens": 10, "outputTokens": 5}
            },
        },
    ]

    assert ClaudeCliAgent._extract_model(events) == "claude-haiku-4-5-20251001"


def test_extract_model_falls_back_to_top_level_field() -> None:
    events = [{"type": "result", "result": "ok", "model": "claude-sonnet-4"}]

    assert ClaudeCliAgent._extract_model(events) == "claude-sonnet-4"


def test_claude_cli_emits_agent_tool_events_during_apply(tmp_path: Path) -> None:
    # Arrange: real db so record_event can write.
    db = tmp_path / "f.sqlite"
    init_db(db)
    agent = ClaudeCliAgent(settings=_settings(db_path=db))
    task = _task(task_id=101)
    streamed = [
        {"type": "system", "session_id": "sess-101"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/a.py"}},
                ]
            },
        },
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "done"}]},
        },
        {"type": "result", "result": "final line\nmore"},
    ]

    # Act
    with patch(
        "foundry.agents.claude_cli.iter_cli_jsonl",
        return_value=iter(streamed),
    ):
        result = agent.apply(task=task, worktree=tmp_path, input="")

    # Assert: contract unchanged + events stored in expected order.
    assert result.response == "final line\nmore"
    assert result.result == "final line"

    events = read_events(db, run_id=101)
    kinds = [(e.kind, e.seq) for e in events]
    kind_names = [k for k, _ in kinds]
    assert "agent_tool" in kind_names
    assert "agent_text" in kind_names
    assert "agent_result" in kind_names

    tool_seq = next(seq for k, seq in kinds if k == "agent_tool")
    result_seq = next(seq for k, seq in kinds if k == "agent_result")
    assert tool_seq < result_seq

    # agent_result payload carries both a short summary (first line) and
    # the full text, so the UI can show a collapsible "full answer" block.
    result_event = next(e for e in events if e.kind == "agent_result")
    assert result_event.payload["summary"] == "final line"
    assert result_event.payload["text"] == "final line\nmore"


def test_record_uses_parent_event_seq_from_context(tmp_path: Path) -> None:
    db = tmp_path / "f.sqlite"
    init_db(db)
    agent = ClaudeCliAgent(settings=_settings(db_path=db))
    task = _task(task_id=202)
    streamed = [
        {"type": "system", "session_id": "sess-202"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/a.py"}},
                    {"type": "text", "text": "thinking"},
                ]
            },
        },
        {"type": "result", "result": "done"},
    ]

    with patch(
        "foundry.agents.claude_cli.iter_cli_jsonl",
        return_value=iter(streamed),
    ):
        with agent_event_context(parent_event_seq=99):
            agent.apply(task=task, worktree=tmp_path, input="")

    events = read_events(db, run_id=202)
    assert events, "expected events to be persisted"
    for ev in events:
        assert ev.parent_event_seq == 99, (
            f"event {ev.kind} seq={ev.seq} has parent_event_seq={ev.parent_event_seq}"
        )


def test_claude_cli_skips_event_emission_without_db_path(tmp_path: Path) -> None:
    agent = ClaudeCliAgent(settings=_settings())  # db_path=None
    streamed = [
        {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]},
        },
        {"type": "result", "result": "ok"},
    ]

    with patch(
        "foundry.agents.claude_cli.iter_cli_jsonl",
        return_value=iter(streamed),
    ):
        # Should not raise even though db_path is None.
        out = agent.apply(task=_task(), worktree=tmp_path, input="")

    assert out.response == "ok"
