from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from .automations.registry import Automation
    from .models import Event

log = structlog.get_logger(__name__)


def compute_session_id(external_id: str, automation_id: str, agent_type: str) -> str:
    """Deterministic session id for an `(event source, automation, agent)` triple.

    Repeated events from the same external channel hashed under the same
    automation and agent type will reuse the same agent session, allowing
    the agent CLI to `--resume` its prior conversation.
    """
    raw = f"{external_id}|{automation_id}|{agent_type}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def resolve_session_id(automation: "Automation", event: "Event") -> str:
    """Pick the session id for ``(automation, event)``.

    If ``automation.session_key`` returns a non-empty string for this event,
    use it as the hash key (so e.g. all messages in a Telegram chat collapse
    into one session). Otherwise fall back to the event's ``external_id``,
    yielding a fresh session per event.
    """
    backend = automation.agent.get("backend", "stub")
    if automation.session_key is not None:
        try:
            key = automation.session_key(event)
        except Exception:
            log.exception(
                "session.key_failed",
                automation_id=automation.id,
                event_id=event.id,
            )
            key = None
        if key:
            return compute_session_id(key, automation.id, backend)
    return compute_session_id(event.external_id, automation.id, backend)


def make_provisional_event(
    *,
    trigger_id: str,
    dedupe_key: str,
    payload: dict[str, Any],
    created_at: str,
) -> "Event":
    """Construct an ``Event`` with ``id=0`` for use **before** the row is
    inserted (e.g. inside ``dispatch_event`` while computing session ids).

    ``trigger_id`` is split on the first dot into ``source``/``kind``.
    """
    from .models import Event

    source, _, kind = trigger_id.partition(".")
    return Event(
        id=0,
        source=source or trigger_id,
        external_id=dedupe_key,
        kind=kind,
        payload=payload,
        created_at=created_at,
    )
