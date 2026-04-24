from __future__ import annotations

from pathlib import Path

from langfuse import observe

from ..agents import AgentSettings, AgentStage, AgentTask, make_agent
from ..config import Settings
from ..models import Task


@observe(name="stage.plan")
def run(task: Task, ctx: dict, worktree_path: Path, settings: Settings) -> dict:
    """Agent-backed plan stage: delegates to the configured plan_agent.

    Returns {"plan": <full agent response>, "summary": <first line>}.
    `ctx` is currently unused (context stage is still a stub).
    """
    agent = make_agent(AgentSettings.from_env(AgentStage.PLAN, db_path=settings.db_path))
    agent_task = AgentTask(
        id=task.id or task.issue_number,
        title=task.issue_title,
        description=task.issue_body,
    )
    r = agent.apply(task=agent_task, worktree=worktree_path, input="")
    return {
        "agent": agent.name,
        "stage": r.stage.value,
        "plan": r.response,
        "summary": r.result,
    }
