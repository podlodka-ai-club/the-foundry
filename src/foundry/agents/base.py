from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


PROMPTS_DIR = Path(__file__).parent / "prompts"


class AgentStage(StrEnum):
    PLAN = "plan"
    IMPLEMENT = "implement"
    VERIFY = "verify"


@dataclass(frozen=True)
class AgentTask:
    id: int
    title: str
    description: str


@dataclass(frozen=True)
class AgentResult:
    stage: AgentStage
    response: str
    result: str
    cost_usd: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None


class CodingAgent(Protocol):
    name: str
    stage: AgentStage

    def apply(
        self,
        task: AgentTask,
        worktree: Path,
        input: str = "",
    ) -> AgentResult: ...

    def get_session_id(self, task: AgentTask) -> str | None: ...


def first_line(text: str, limit: int = 200) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:limit]
    return ""


def load_prompt_template(stage: AgentStage) -> str:
    return (PROMPTS_DIR / f"{stage.value}.md").read_text(encoding="utf-8")


def build_fresh_prompt(stage: AgentStage, task: AgentTask, input: str) -> str:
    """Compose the initial prompt the first time an agent sees a task.

    Template lives at `src/foundry/agents/prompts/<stage>.md` and owns the
    role description, rules, and output format. Caller only supplies `input`
    (plan text for implement, diff for verify, clarification hints, ...).
    """
    template = load_prompt_template(stage)
    return template.format(
        title=task.title,
        description=task.description,
        input=input,
    )


def run_cli_jsonl(
    cmd: list[str],
    *,
    cwd: Path,
    timeout_sec: int,
    env: dict[str, str] | None = None,
) -> list[dict]:
    """Run a CLI that emits newline-delimited JSON events on stdout.

    Raises subprocess.CalledProcessError on non-zero exit and TimeoutExpired on
    timeout — callers treat both as retriable infra failures.
    """
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=True,
        env=env,
    )
    events: list[dict] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            events.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return events
