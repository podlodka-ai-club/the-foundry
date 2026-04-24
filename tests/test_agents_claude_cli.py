from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from foundry.agents import AgentSettings, AgentStage, AgentTask
from foundry.agents.claude_cli import ClaudeCliAgent


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

    with patch("foundry.agents.claude_cli.run_cli_jsonl") as run:
        run.side_effect = [fresh_events, resume_events]

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
        "foundry.agents.claude_cli.run_cli_jsonl",
        return_value=[{"type": "result", "result": "ok"}],
    ) as run:
        agent.apply(task=_task(), worktree=tmp_path, input="")

    cmd = run.call_args.args[0]
    assert cmd[cmd.index("--model") + 1] == "opus"
    assert cmd[cmd.index("--max-turns") + 1] == "11"
    assert "--permission-mode" in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "acceptEdits"


def test_apply_runs_in_worktree_cwd(tmp_path: Path) -> None:
    agent = ClaudeCliAgent(settings=_settings())

    with patch(
        "foundry.agents.claude_cli.run_cli_jsonl",
        return_value=[{"type": "result", "result": "ok"}],
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
