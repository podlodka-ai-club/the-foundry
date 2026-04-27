from __future__ import annotations

from ..config import Settings
from ..models import Task


def run(task: Task, ctx: dict, settings: Settings) -> dict:
    """STUB: returns a hardcoded single-step plan. Real LLM planner lands Day 3+."""
    return {
        "steps": [
            {
                "file": "README.md",
                "action": "append_line",
                "line": f"foundry-bot: task #{task.issue_number} — {task.issue_title}",
            }
        ]
    }
