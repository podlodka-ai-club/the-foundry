from __future__ import annotations

from .base import EmitFn, Listener

__all__ = ["EmitFn", "Listener", "build_listeners"]


def build_listeners(settings):  # type: ignore[no-untyped-def]
    """Construct default listener set from settings.

    Honours ``settings.listeners_enabled`` — empty tuple means 'all'.
    Implementation lives in :mod:`foundry.listeners._factory` to avoid
    circular imports at module-load time.
    """
    from ._factory import build_listeners as _build

    return _build(settings)
