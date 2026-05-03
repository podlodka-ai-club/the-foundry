from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from foundry.agents import AgentSettings, AgentTask
from foundry.agents.opencode_cli import OpencodeCliAgent


def _task(task_id: int = 1) -> AgentTask:
    return AgentTask(id=task_id, title="t", description="d")


def _settings(**overrides: object) -> AgentSettings:
    defaults: dict = {
        "backend": "opencode_cli",
        "timeout_sec": 60,
        "max_turns": 3,
        "model": "openrouter/anthropic/claude-haiku-4.5",
    }
    defaults.update(overrides)
    return AgentSettings(**defaults)  # type: ignore[arg-type]


def test_extract_session_id_from_top_level_sessionID() -> None:
    events = [
        {"type": "step_start", "sessionID": "ses_abc"},
        {"type": "text", "sessionID": "ses_abc", "part": {"text": "hi"}},
    ]

    assert OpencodeCliAgent._extract_session_id(events) == "ses_abc"


def test_extract_session_id_falls_back_to_part_sessionID() -> None:
    events = [{"type": "text", "part": {"sessionID": "ses_from_part"}}]

    assert OpencodeCliAgent._extract_session_id(events) == "ses_from_part"


def test_extract_session_id_returns_none_when_missing() -> None:
    assert OpencodeCliAgent._extract_session_id([{"type": "text", "part": {}}]) is None


def test_extract_final_text_concatenates_text_events_in_order() -> None:
    events = [
        {"type": "step_start"},
        {"type": "text", "part": {"text": "Hello "}},
        {"type": "step_start"},
        {"type": "text", "part": {"text": "world"}},
        {"type": "step_finish"},
    ]

    assert OpencodeCliAgent._extract_final_text(events) == "Hello world"


def test_extract_final_text_returns_empty_when_no_text_events() -> None:
    events = [{"type": "step_finish"}]

    assert OpencodeCliAgent._extract_final_text(events) == ""


def test_apply_caches_session_id_and_resumes_next_call(tmp_path: Path) -> None:
    agent = OpencodeCliAgent(settings=_settings())
    task = _task(task_id=11)
    fresh = [
        {"type": "step_start", "sessionID": "ses_11"},
        {"type": "text", "sessionID": "ses_11", "part": {"text": "done"}},
    ]
    resume = [{"type": "text", "sessionID": "ses_11", "part": {"text": "again"}}]

    with patch("foundry.agents.opencode_cli.run_cli_jsonl") as run:
        run.side_effect = [fresh, resume]
        first = agent.apply(task=task, worktree=tmp_path, input="hi")
        second = agent.apply(task=task, worktree=tmp_path, input="more")

    assert first.response == "done"
    assert second.response == "again"
    assert agent.get_session_id(task) == "ses_11"
    fresh_cmd = run.call_args_list[0].args[0]
    resume_cmd = run.call_args_list[1].args[0]
    assert "--session" not in fresh_cmd
    assert resume_cmd[resume_cmd.index("--session") + 1] == "ses_11"


def test_apply_passes_model_dir_and_format(tmp_path: Path) -> None:
    agent = OpencodeCliAgent(settings=_settings(model="openrouter/x-ai/grok"))

    with patch(
        "foundry.agents.opencode_cli.run_cli_jsonl",
        return_value=[{"type": "text", "sessionID": "s", "part": {"text": "ok"}}],
    ) as run:
        agent.apply(task=_task(), worktree=tmp_path, input="")

    cmd = run.call_args.args[0]
    assert cmd[:2] == ["opencode", "run"]
    assert cmd[cmd.index("--format") + 1] == "json"
    assert cmd[cmd.index("--dir") + 1] == str(tmp_path)
    assert cmd[cmd.index("-m") + 1] == "openrouter/x-ai/grok"
    assert run.call_args.kwargs["cwd"] == tmp_path


def test_extract_usage_from_metadata_tokens() -> None:
    events = [
        {"type": "text", "part": {"text": "hi"}},
        {
            "type": "step_finish",
            "metadata": {
                "tokens": {
                    "input": 200,
                    "output": 60,
                    "cache": {"read": 500, "write": 10},
                }
            },
        },
    ]

    got = OpencodeCliAgent._extract_usage(events)

    assert got == {
        "input": 200,
        "output": 60,
        "cache_read_input": 500,
        "cache_creation_input": 10,
    }


def test_extract_usage_from_top_level_tokens() -> None:
    events = [{"type": "step_finish", "tokens": {"input": 15, "output": 7}}]

    assert OpencodeCliAgent._extract_usage(events) == {"input": 15, "output": 7}


def test_extract_usage_returns_none_when_missing() -> None:
    events = [{"type": "text", "part": {"text": "hi"}}]

    assert OpencodeCliAgent._extract_usage(events) is None
