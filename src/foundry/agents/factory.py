from __future__ import annotations

from .base import CodingAgent
from .claude_cli import ClaudeCliAgent
from .codex_cli import CodexCliAgent
from .config import AgentSettings
from .opencode_cli import OpencodeCliAgent
from .stub import StubAgent


class UnknownBackendError(ValueError):
    pass


def make_agent(settings: AgentSettings) -> CodingAgent:
    match settings.backend:
        case "stub":
            return StubAgent(settings=settings)
        case "claude_cli":
            return ClaudeCliAgent(settings=settings)
        case "codex_cli":
            return CodexCliAgent(settings=settings)
        case "opencode_cli":
            return OpencodeCliAgent(settings=settings)
        case other:
            raise UnknownBackendError(f"unknown CODING_AGENT={other!r}")
