from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class EmitFn(Protocol):
    """Listener-side handle to ``dispatch_event``.

    A listener emits one of the canonical ``trigger_id``s declared in
    :mod:`foundry.triggers` (or a ``cron.<rule_id>`` namespaced one). The
    dispatcher creates a ``PENDING`` run for every subscribed automation
    in the same transaction as the event insert.
    """

    async def __call__(
        self,
        *,
        trigger_id: str,
        dedupe_key: str,
        payload: dict[str, Any],
        parent_event_id: int | None = None,
    ) -> int | None: ...


@runtime_checkable
class Listener(Protocol):
    """Long-running source of external events.

    ``id`` is the listener's stable identifier (used for supervision /
    settings.listeners_enabled). ``source`` is a coarse grouping used by
    :func:`foundry.state.last_external_id` so listeners can resume after a
    restart without keeping a separate cursor.
    """

    id: str
    source: str

    async def listen(self, emit: EmitFn) -> None: ...
