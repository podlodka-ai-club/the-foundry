from __future__ import annotations

from pathlib import Path

from ..events import record_event
from .base import AgentResult, AgentStage, AgentTask, first_line
from .config import AgentSettings
from .context import get_parent_event_seq


class StubAgent:
    """Offline agent — no external calls. Used for CI and local smoke tests.

    Bound to one stage at construction time. Behavior per stage:
    - PLAN: returns a trivial plan text.
    - IMPLEMENT: appends a single line to README.md in the worktree.
    - VERIFY: always passes.
    """

    name = "stub"

    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings
        self.stage = settings.stage

    def apply(
        self,
        task: AgentTask,
        worktree: Path,
        input: str = "",
    ) -> AgentResult:
        self._emit(task, kind="agent_thinking", payload={"text": "stub: thinking..."})

        match self.stage:
            case AgentStage.PLAN:
                self._emit(
                    task,
                    kind="agent_tool",
                    payload={"tool": "Read", "detail": "README.md"},
                )
                response = (
                    f"stub plan for issue #{task.id}\n\n"
                    f"Title: {task.title}\n"
                    f"Plan: append one line to README.md"
                )
            case AgentStage.IMPLEMENT:
                self._emit(
                    task,
                    kind="agent_tool",
                    payload={"tool": "Edit", "detail": "README.md"},
                )
                response = self._append_readme_line(worktree, task)
            case AgentStage.VERIFY:
                self._emit(
                    task,
                    kind="agent_tool",
                    payload={"tool": "Bash", "detail": "echo ok"},
                )
                response = "PASS\nstub always verifies PASS"
            case _:
                raise NotImplementedError(f"unknown stage: {self.stage!r}")

        summary = first_line(response)
        self._emit(task, kind="agent_result", payload={"summary": summary})

        return AgentResult(
            stage=self.stage,
            response=response,
            result=summary,
        )

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
            stage=self.stage.value,
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
