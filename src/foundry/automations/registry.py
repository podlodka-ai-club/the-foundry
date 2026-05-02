from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Automation:
    id: str
    name: str
    description: str
    triggers: tuple[str, ...]
    agent: dict[str, Any]
    prompt_path: str
    skills: tuple[str, ...] = ()


DEV_TASK = Automation(
    id="dev_task",
    name="GitHub issue → PR",
    description="Implement labeled GitHub issues; will be reworked in C5.",
    triggers=("github_issues",),
    agent={"backend": "claude_cli", "model": None},
    prompt_path="prompts/dev_task.md",
    skills=(),
)


AUTOMATIONS: list[Automation] = [DEV_TASK]


def get_automation(automation_id: str) -> Automation | None:
    return next((a for a in AUTOMATIONS if a.id == automation_id), None)


def automations_for_trigger(trigger_id: str) -> list[Automation]:
    return [a for a in AUTOMATIONS if trigger_id in a.triggers]
