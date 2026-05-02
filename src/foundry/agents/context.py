from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

_current_parent_event_seq: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "foundry_parent_event_seq", default=None,
)


def get_parent_event_seq() -> int | None:
    """Return the parent_event_seq for the current agent invocation, or None.

    Set inside `agent_event_context(...)` by the caller (e.g. the MCP runner)
    so that downstream `record_event(...)` calls inside the agent automatically
    nest under the framing event of the sub-agent call.
    """
    return _current_parent_event_seq.get()


@contextmanager
def agent_event_context(*, parent_event_seq: int | None) -> Iterator[None]:
    """Bind a parent_event_seq for the duration of the context.

    Nested contexts restore the outer value on exit (contextvars semantics).
    """
    token = _current_parent_event_seq.set(parent_event_seq)
    try:
        yield
    finally:
        _current_parent_event_seq.reset(token)
