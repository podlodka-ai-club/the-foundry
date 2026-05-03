from __future__ import annotations

from pathlib import Path

from ..events import record_event
from .base import AgentResult, AgentTask, first_line
from .config import AgentSettings
from .context import get_parent_event_seq


_AGENT_STAGE = "agent"


class StubAgent:
    """Offline agent — no external calls. Used for CI and local smoke tests.

    Behaviour: append one line to README.md in the worktree (creating it if
    missing) and return a deterministic summary. Mirrors a tiny subset of
    `agent_tool` / `agent_result` events into ``run_events`` when a
    ``db_path`` is configured, so observability tests have something to
    assert on.
    """

    name = "stub"

    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings

    def apply(
        self,
        task: AgentTask,
        worktree: Path,
        input: str = "",
    ) -> AgentResult:
        self._emit(task, kind="agent_thinking", payload={"text": "stub: thinking..."})
        self._emit(
            task,
            kind="agent_tool",
            payload={"tool": "Edit", "detail": "README.md"},
        )
        response = self._append_readme_line(worktree, task)
        summary = first_line(response)
        self._emit(task, kind="agent_result", payload={"summary": summary})

        return AgentResult(response=response, result=summary)

    def _emit(self, task: AgentTask, *, kind: str, payload: dict) -> None:
        """Emit a synthetic event for UI observability.

        Skipped gracefully when no db_path is configured (e.g. unit tests that
        instantiate StubAgent in isolation). When invoked from a sub-agent
        context, events nest under the framing `agent_call_started` via
        `parent_event_seq`.
        """
        if self._settings.db_path is None:
            return
        record_event(
            self._settings.db_path,
            run_id=task.id,
            stage=_AGENT_STAGE,
            kind=kind,
            payload=payload,
            parent_event_seq=get_parent_event_seq(),
        )

    def get_session_id(self, task: AgentTask) -> str | None:
        return None

    @staticmethod
    def _append_readme_line(worktree: Path, task: AgentTask) -> str:
        target = worktree / "README.md"
        line = f"foundry-bot: task #{task.id} — {task.title}\n"
        needs_leading_newline = False
        if target.exists() and target.stat().st_size > 0:
            with target.open("rb") as r:
                r.seek(-1, 2)
                needs_leading_newline = r.read(1) != b"\n"
        payload = ("\n" if needs_leading_newline else "") + line
        with target.open("a", encoding="utf-8") as f:
            f.write(payload)
        return f"appended 1 line to README.md ({len(payload)} bytes) for issue #{task.id}"
