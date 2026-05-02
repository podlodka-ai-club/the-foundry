from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class EmitFn(Protocol):
    async def __call__(
        self,
        *,
        external_id: str,
        kind: str,
        payload: dict[str, Any],
        parent_event_id: int | None = None,
    ) -> int | None: ...


@runtime_checkable
class Listener(Protocol):
    """Long-running source of external events.

    Trigger naming convention (used by C4 orchestrator subscription):
    - ``"github_issues"`` — emitted by :class:`GithubIssuesListener`.
    - ``"cron:<rule_id>"`` — cron rules expose themselves as ``cron:<rule_id>``;
      parsing into source ``cron`` plus rule id is C4 work.
    - ``"discord"`` — emitted by :class:`DiscordListener` (stub for now).
    """

    id: str
    source: str

    async def listen(self, emit: EmitFn) -> None: ...
