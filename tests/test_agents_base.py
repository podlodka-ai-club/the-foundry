from __future__ import annotations

from foundry.agents import AgentStage, AgentTask, first_line
from foundry.agents.base import build_fresh_prompt


def test_first_line_returns_first_non_empty_line() -> None:
    result = first_line("\n\n  hello world  \nsecond\n")

    assert result == "hello world"


def test_first_line_truncates_to_limit() -> None:
    result = first_line("a" * 500, limit=10)

    assert result == "a" * 10


def test_first_line_on_empty_input_returns_empty_string() -> None:
    assert first_line("") == ""
    assert first_line("\n   \n") == ""


def test_build_fresh_prompt_substitutes_title_description_and_input() -> None:
    task = AgentTask(id=1, title="My title", description="Do X")

    prompt = build_fresh_prompt(AgentStage.PLAN, task, input="hints here")

    assert "My title" in prompt
    assert "Do X" in prompt
    assert "hints here" in prompt


def test_build_fresh_prompt_loads_different_templates_per_stage() -> None:
    task = AgentTask(id=1, title="T", description="D")

    plan_prompt = build_fresh_prompt(AgentStage.PLAN, task, input="")
    verify_prompt = build_fresh_prompt(AgentStage.VERIFY, task, input="")

    assert plan_prompt != verify_prompt
