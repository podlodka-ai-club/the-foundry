from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from foundry import triggers
from foundry.models import Event


WorkspaceKind = Literal["git_worktree", "pr_worktree", "fixed", "ephemeral"]


@dataclass(frozen=True)
class Automation:
    """Declarative automation record.

    The agent always runs in some directory. ``workspace`` picks how that
    directory is materialized:

    - ``"git_worktree"`` → fresh worktree under ``WORKTREE_ROOT/task-{run_id}``
      branched off ``SOURCE_REPO/main``. Used for ``dev_task``.
    - ``"pr_worktree"`` → per-PR detached worktree under the
      ``pr_review_base_path`` umbrella, at the PR's ``head_sha``, with the
      developer's untracked configs rsynced over. Used for ``pr_review``.
    - ``"fixed"`` → use ``cwd`` verbatim. The directory must exist (the
      orchestrator ``mkdir -p`` it on first use). Used for chat-style
      automations whose Claude CLI ``--resume`` is keyed by cwd hash and
      therefore needs a stable path. ``cwd`` is required.
    - ``"ephemeral"`` → throwaway ``WORKTREE_ROOT/run-{run_id}/`` dir. The
      default; works for cron / utility automations that don't touch a repo.

    The agent is given that directory as its ``cwd``, so it auto-discovers
    any ``.claude/commands/*.md``, ``.mcp.json``, and ``CLAUDE.md`` already
    living there. Foundry only adds its small MCP server with the
    :data:`foundry.skills.SKILL_REGISTRY` (currently
    ``commit_and_push_pr`` / ``telegram_reply`` / ``wait_for_human``) plus
    ``call_subagent`` — no per-automation whitelist. Run-level signalling
    is done via a ``STATUS:`` marker in the agent's final reply parsed by
    :mod:`foundry.status_marker`, not via MCP tools.

    ``session_key`` lets an automation collapse multiple events into a
    single rolling agent session. The callable receives the trigger
    ``Event``; if it returns a non-empty string, the orchestrator uses it
    as the session id so subsequent events with the same key reuse (and
    resume) the prior agent CLI session. Returning ``None`` falls back to
    per-event hashing.
    """

    id: str
    name: str
    description: str
    triggers: tuple[str, ...]
    agent: dict[str, Any]
    prompt_path: str
    workspace: WorkspaceKind = "ephemeral"
    cwd: Path | None = None
    session_key: Callable[[Event], str | None] | None = None

    def __post_init__(self) -> None:
        if self.workspace == "fixed" and self.cwd is None:
            raise ValueError(
                f"Automation {self.id!r}: workspace='fixed' requires cwd"
            )


DEV_TASK = Automation(
    id="dev_task",
    name="GitHub issue → PR",
    description="Реализует GitHub issue и открывает PR.",
    triggers=(triggers.GITHUB_ISSUE_OPENED,),
    agent={"backend": "claude_cli", "model": "sonnet"},
    prompt_path="prompts/dev_task.md",
    workspace="git_worktree",
)


def _telegram_session_key(event: Event) -> str | None:
    """Collapse all messages from one Telegram chat into a single session."""
    chat_id = (event.payload or {}).get("chat_id")
    return f"tg:{chat_id}" if chat_id is not None else None


TG_CHAT = Automation(
    id="tg_chat",
    name="Telegram chat assistant",
    description="Отвечает на сообщения в приватном Telegram-чате.",
    triggers=(triggers.TELEGRAM_MESSAGE,),
    agent={"backend": "claude_cli", "model": "sonnet"},
    prompt_path="prompts/tg_chat.md",
    # Stable cwd: agent spawns in user's main project umbrella so it sees
    # all the code AND so Claude CLI's `--resume` works (sessions indexed
    # by cwd hash — a moving cwd would break multi-turn chat).
    workspace="fixed",
    cwd=Path("~/w/datura/lium/main"),
    session_key=_telegram_session_key,
)


def _pr_review_session_key(event: Event) -> str | None:
    payload = event.payload or {}
    repo = payload.get("repo")
    number = payload.get("number")
    if not repo or number is None:
        return None
    return f"pr-review:{repo}#{number}"


PR_REVIEW = Automation(
    id="pr_review",
    name="PR review",
    description="Локально проверяет PR и пишет ревью в run_events.",
    triggers=(triggers.GITHUB_PR_REVIEW_REQUESTED, triggers.GITHUB_PR_AUTHORED),
    agent={"backend": "claude_cli", "model": "sonnet"},
    prompt_path="prompts/pr_review.md",
    workspace="pr_worktree",
    session_key=_pr_review_session_key,
)


AUTOMATIONS: list[Automation] = [DEV_TASK, TG_CHAT, PR_REVIEW]


def get_automation(automation_id: str) -> Automation | None:
    return next((a for a in AUTOMATIONS if a.id == automation_id), None)


def automations_for_trigger(trigger_id: str) -> list[Automation]:
    return [a for a in AUTOMATIONS if trigger_id in a.triggers]
