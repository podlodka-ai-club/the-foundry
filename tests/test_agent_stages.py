from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from foundry.agents import AgentResult, AgentStage
from foundry.config import Settings
from foundry.models import Task
from foundry.stages import agent_implement, agent_plan


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        source_repo="owner/sandbox",
        target_repo="owner/sandbox",
        issue_label="agent-task",
        worktree_root=tmp_path / "worktrees",
        db_path=tmp_path / "foundry.sqlite",
        poll_interval_seconds=30,
    )


def _task() -> Task:
    task = Task(
        repo="owner/sandbox",
        issue_number=101,
        issue_title="add endpoint",
        issue_body="please add /ping",
    )
    task.id = 5
    return task


def _fake_agent(stage: AgentStage, response: str, result: str) -> MagicMock:
    agent = MagicMock()
    agent.name = "fake"
    agent.apply.return_value = AgentResult(stage=stage, response=response, result=result)
    return agent


def test_agent_plan_delegates_to_plan_agent_and_returns_full_response(tmp_path: Path) -> None:
    fake = _fake_agent(AgentStage.PLAN, response="full plan text\nstep 1", result="full plan text")
    ctx = {
        "languages": [{"language": "Python", "files": 2}],
        "manifest_files": ["pyproject.toml"],
        "test_commands": ["pytest -q"],
        "keywords": ["endpoint"],
        "relevant_files": [{"path": "src/api/main.py", "matched_keywords": ["endpoint"]}],
    }

    with patch("foundry.stages.agent_plan.make_agent", return_value=fake) as make:
        out = agent_plan.run(_task(), ctx=ctx, worktree_path=tmp_path, settings=_settings(tmp_path))

    make.assert_called_once()
    assert make.call_args.args[0].stage is AgentStage.PLAN
    call = fake.apply.call_args
    assert call.kwargs["worktree"] == tmp_path
    assert "## Repository context" in call.kwargs["input"]
    assert "`src/api/main.py`" in call.kwargs["input"]
    assert call.kwargs["task"].id == 5
    assert call.kwargs["task"].title == "add endpoint"
    assert out == {
        "agent": "fake",
        "stage": "plan",
        "plan": "full plan text\nstep 1",
        "summary": "full plan text",
        "cost_usd": None,
        "tokens_in": None,
        "tokens_out": None,
    }


def test_agent_plan_falls_back_to_issue_number_when_task_has_no_db_id(tmp_path: Path) -> None:
    task = _task()
    task.id = None
    fake = _fake_agent(AgentStage.PLAN, "x", "x")

    with patch("foundry.stages.agent_plan.make_agent", return_value=fake):
        agent_plan.run(task, ctx={}, worktree_path=tmp_path, settings=_settings(tmp_path))

    assert fake.apply.call_args.kwargs["task"].id == 101


def test_agent_implement_feeds_plan_text_to_implement_agent(tmp_path: Path) -> None:
    plan = {"plan": "step A\nstep B", "summary": "step A"}
    fake = _fake_agent(AgentStage.IMPLEMENT, response="changed 2 files", result="changed 2 files")

    with patch("foundry.stages.agent_implement.make_agent", return_value=fake) as make:
        out = agent_implement.run(_task(), plan, worktree_path=tmp_path, settings=_settings(tmp_path))

    assert make.call_args.args[0].stage is AgentStage.IMPLEMENT
    assert fake.apply.call_args.kwargs["input"] == "step A\nstep B"
    assert out == {
        "agent": "fake",
        "stage": "implement",
        "result": "changed 2 files",
        "response": "changed 2 files",
        "cost_usd": None,
        "tokens_in": None,
        "tokens_out": None,
    }


def test_agent_implement_handles_plan_without_plan_key(tmp_path: Path) -> None:
    fake = _fake_agent(AgentStage.IMPLEMENT, "ok", "ok")

    with patch("foundry.stages.agent_implement.make_agent", return_value=fake):
        agent_implement.run(_task(), plan={"steps": []}, worktree_path=tmp_path, settings=_settings(tmp_path))

    assert fake.apply.call_args.kwargs["input"] == ""
