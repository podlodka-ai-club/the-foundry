from __future__ import annotations

from pathlib import Path

from langfuse import observe

from ..agents import AgentSettings, AgentStage, AgentTask, make_agent
from ..config import Settings
from ..models import Task


@observe(name="stage.agent_verify")
def run(task: Task, worktree_path: Path, diff_text: str, settings: Settings) -> dict:
    """Agent-backed reviewer: hands a diff to the configured verify_agent.

    Mirrors the shape of `agent_implement.run`. The agent's prompt template
    (`agents/prompts/verify.md`) substitutes `diff_text` into `{input}` and
    expects the response's first line to be `PASS` or `FAIL: <reason>`. Parsing
    that verdict is the orchestrator's job, not this wrapper's.
    """
    agent = make_agent(AgentSettings.from_env(AgentStage.VERIFY, db_path=settings.db_path))
    agent_task = AgentTask(
        id=task.id or task.issue_number,
        title=task.issue_title,
        description=task.issue_body,
    )
    r = agent.apply(task=agent_task, worktree=worktree_path, input=diff_text)
    return {
        "agent": agent.name,
        "stage": r.stage.value,
        "result": r.result,
        "response": r.response,
        "cost_usd": r.cost_usd,
        "tokens_in": r.tokens_in,
        "tokens_out": r.tokens_out,
    }
