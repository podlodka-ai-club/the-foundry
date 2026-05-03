"""MCP skills exposed to the agent at runtime.

Trimmed to side-effect tools that genuinely need MCP:

- ``commit_and_push_pr`` — non-trivial git/gh sequence with proper retry
  and failure surface; would be fragile as raw bash in the prompt.
- ``telegram_reply`` — keeps the bot token inside the MCP subprocess so
  the agent never sees it (security boundary).
- ``wait_for_human`` — active state transition (``status=WAITING``); the
  agent must stop, not finish, which only the orchestrator can manage.

Control-plane signalling (``mark_done`` / ``mark_failed``) was removed in
favour of a ``STATUS:`` marker in the agent's final reply — see
:mod:`foundry.status_marker`. Worktree-introspection skills
(``open_worktree`` / ``open_pr_worktree``) were dropped: the orchestrator
already prepares the worktree and exposes paths via ``FOUNDRY_*`` env
vars. Domain helpers (``react_emoji`` / ``run_tests``) were dropped: the
agent can call ``gh``/``pytest`` via ``Bash`` directly.
"""

from __future__ import annotations

from typing import Any, Callable

from .pr import commit_and_push_pr_impl
from .telegram_reply import telegram_reply_impl
from .wait_for_human import wait_for_human_impl

SKILL_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "commit_and_push_pr": commit_and_push_pr_impl,
    "telegram_reply": telegram_reply_impl,
    "wait_for_human": wait_for_human_impl,
}

__all__ = ["SKILL_REGISTRY"]
