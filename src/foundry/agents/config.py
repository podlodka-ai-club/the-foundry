from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from ..security import is_safe_agent_mode
from .base import AgentStage


DEFAULT_MAX_TURNS: dict[AgentStage, int] = {
    AgentStage.PLAN: 50,
    AgentStage.IMPLEMENT: 50,
    AgentStage.VERIFY: 20,
}


@dataclass(frozen=True)
class AgentSettings:
    """Settings for a single-stage agent.

    One agent instance is bound to one stage at construction time. To run a
    full pipeline you build three separate agents with three separate
    settings — they can differ in backend, model, turn cap, and timeout.
    """

    stage: AgentStage
    backend: str = "stub"
    timeout_sec: int = 600
    max_turns: int = 30
    model: str = "haiku"
    db_path: Path | None = None
    safe_agent_mode: bool = True
    sandbox_mode: str | None = None

    @classmethod
    def from_env(cls, stage: AgentStage, db_path: Path | None = None) -> AgentSettings:
        """Load settings for `stage` from environment.

        Per-stage env vars (e.g. `AGENT_PLAN_MODEL`) win over global ones
        (`AGENT_MODEL`); global wins over hard-coded defaults.
        """
        load_dotenv()
        key = stage.value.upper()
        model = os.getenv(f"AGENT_{key}_MODEL") or os.getenv("AGENT_MODEL", "haiku")
        timeout = int(
            os.getenv(f"AGENT_{key}_TIMEOUT_SEC")
            or os.getenv("AGENT_TIMEOUT_SEC", "600")
        )
        max_turns = int(
            os.getenv(f"AGENT_{key}_MAX_TURNS")
            or os.getenv("AGENT_MAX_TURNS", str(DEFAULT_MAX_TURNS[stage]))
        )
        sandbox_mode = (
            os.getenv(f"AGENT_{key}_SANDBOX_MODE")
            or os.getenv("AGENT_SANDBOX_MODE")
            or os.getenv("CODEX_SANDBOX_MODE")
        )
        return cls(
            stage=stage,
            backend=os.getenv(f"AGENT_{key}_BACKEND") or os.getenv("CODING_AGENT", "stub"),
            timeout_sec=timeout,
            max_turns=max_turns,
            model=model,
            db_path=db_path,
            safe_agent_mode=is_safe_agent_mode(
                os.getenv(f"AGENT_{key}_SAFE_MODE")
                or os.getenv("SAFE_AGENT_MODE", "true")
            ),
            sandbox_mode=sandbox_mode,
        )
