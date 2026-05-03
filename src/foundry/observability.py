from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

import structlog

log = structlog.get_logger()

_enabled = False


def init_langfuse() -> bool:
    """Initialize Langfuse from env. No-op if keys missing.

    Safe to call multiple times; first call with valid keys wins.
    Returns True when tracing is active, False otherwise.
    """
    global _enabled
    if _enabled:
        return True
    if not os.getenv("LANGFUSE_SECRET_KEY") or not os.getenv("LANGFUSE_PUBLIC_KEY"):
        log.info("langfuse.disabled", reason="missing keys")
        return False
    try:
        from langfuse import Langfuse

        Langfuse()
    except Exception as e:
        log.warning("langfuse.init_failed", error=str(e))
        return False
    _enabled = True
    log.info("langfuse.enabled", host=os.getenv("LANGFUSE_HOST", "default"))
    return True


def flush() -> None:
    """Flush pending traces. Call at end of `run_once` to avoid losing data."""
    if not _enabled:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception as e:
        log.warning("langfuse.flush_failed", error=str(e))


@contextmanager
def track_generation(
    name: str,
    *,
    model: str | None = None,
    input: Any = None,
) -> Iterator[Any]:
    """Create a Langfuse generation span around an LLM call.

    Yields the generation object (or None if Langfuse is disabled) so the
    caller can attach output/usage/model after the call returns.
    """
    if not _enabled:
        yield None
        return
    try:
        from langfuse import get_client

        client = get_client()
    except Exception as e:
        log.warning("langfuse.generation_setup_failed", error=str(e))
        yield None
        return
    try:
        with client.start_as_current_observation(
            name=name, as_type="generation", model=model, input=input
        ) as gen:
            yield gen
    except Exception as e:
        log.warning("langfuse.generation_failed", error=str(e))
        yield None


def update_generation(
    gen: Any,
    *,
    output: Any = None,
    usage: dict[str, int] | None = None,
    model: str | None = None,
) -> None:
    """Attach output/usage/model to an open generation. No-op if gen is None."""
    if gen is None:
        return
    kwargs: dict[str, Any] = {}
    if output is not None:
        kwargs["output"] = output
    if usage:
        kwargs["usage_details"] = usage
    if model:
        kwargs["model"] = model
    if not kwargs:
        return
    try:
        gen.update(**kwargs)
    except Exception as e:
        log.warning("langfuse.generation_update_failed", error=str(e))
