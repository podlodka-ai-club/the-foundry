from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubAgent:
    """A registered sub-agent that the top-level agent can invoke via MCP.

    `backend` matches the values accepted by `make_agent` (`stub`, `claude_cli`,
    `codex_cli`, `opencode_cli`). The real prompt-driven sub-agents land in C5;
    for now only the `echo` stub exists for smoke tests.
    """

    name: str
    description: str
    backend: str
    model: str | None
    prompt_path: str | None


SUBAGENTS: list[SubAgent] = [
    SubAgent(
        name="echo",
        description="Stub sub-agent for smoke tests; returns the prompt verbatim.",
        backend="stub",
        model=None,
        prompt_path=None,
    ),
]


def get_subagent(name: str) -> SubAgent | None:
    return next((s for s in SUBAGENTS if s.name == name), None)
