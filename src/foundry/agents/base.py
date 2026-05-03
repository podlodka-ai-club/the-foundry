from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class AgentTask:
    id: int
    title: str
    description: str


@dataclass(frozen=True)
class AgentResult:
    response: str
    result: str
    cost_usd: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None


class CodingAgent(Protocol):
    name: str

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


def run_cli_jsonl(cmd: list[str], *, cwd: Path, timeout_sec: int) -> list[dict]:
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
