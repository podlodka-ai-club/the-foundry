from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_MAX_TURNS = 50


@dataclass(frozen=True)
class AgentSettings:
    """Settings for one agent invocation.

    Each automation builds an agent from these settings; nothing here is
    automation-specific — the orchestrator fills in ``backend`` / ``model``
    from the automation record and adds per-run paths (``db_path``,
    ``mcp_config``, ``resume_session_id``).
    """

    backend: str = "stub"
    timeout_sec: int = 600
    max_turns: int = DEFAULT_MAX_TURNS
    model: str = "haiku"
    db_path: Path | None = None
    mcp_config: Path | None = None
    # Session id to resume into when no per-task cache hit exists. Used by
    # C6 retry-flow.
    resume_session_id: str | None = None

    @classmethod
    def from_env(cls, db_path: Path | None = None) -> AgentSettings:
        """Load settings from environment.

        Reads ``CODING_AGENT`` / ``AGENT_MODEL`` / ``AGENT_TIMEOUT_SEC`` /
        ``AGENT_MAX_TURNS`` / ``AGENT_MCP_CONFIG``. No per-stage overrides —
        the staged pipeline is gone, so one env-var per knob is enough.
        """
        load_dotenv()
        mcp_config_raw = os.getenv("AGENT_MCP_CONFIG")
        mcp_config = Path(mcp_config_raw) if mcp_config_raw else None
        return cls(
            backend=os.getenv("CODING_AGENT", "stub"),
            timeout_sec=int(os.getenv("AGENT_TIMEOUT_SEC", "600")),
            max_turns=int(os.getenv("AGENT_MAX_TURNS", str(DEFAULT_MAX_TURNS))),
            model=os.getenv("AGENT_MODEL", "haiku"),
            db_path=db_path,
            mcp_config=mcp_config,
        )
