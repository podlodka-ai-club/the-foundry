from __future__ import annotations

import hashlib


def compute_session_id(external_id: str, automation_id: str, agent_type: str) -> str:
    """Deterministic session id for an `(event source, automation, agent)` triple.

    Repeated events from the same external channel hashed under the same
    automation and agent type will reuse the same agent session, allowing
    the agent CLI to `--resume` its prior conversation.
    """
    raw = f"{external_id}|{automation_id}|{agent_type}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]
