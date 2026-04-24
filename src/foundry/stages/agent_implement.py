from __future__ import annotations

from pathlib import Path

from langfuse import observe

from ..agents import AgentSettings, AgentStage, AgentTask, make_agent
from ..config import Settings
from ..models import Task


@observe(name="stage.implement")
def run(task: Task, plan: dict, worktree_path: Path, settings: Settings) -> dict:
    """Agent-backed implement stage: delegates to the configured implement_agent.

    Same signature as `stages.implement.run`. The plan dict may come from
    `agent_plan` (key `plan` with full text) or from the old stub (key
    `steps`); both are handled.
    """
    agent = make_agent(AgentSettings.from_env(AgentStage.IMPLEMENT, db_path=settings.db_path))
    agent_task = AgentTask(
        id=task.id or task.issue_number,
        title=task.issue_title,
        description=task.issue_body,
    )
    plan_text = plan.get("plan") or ""
    r = agent.apply(task=agent_task, worktree=worktree_path, input=plan_text)
    return {
        "agent": agent.name,
        "stage": r.stage.value,
        "result": r.result,
        "response": r.response,
    }
