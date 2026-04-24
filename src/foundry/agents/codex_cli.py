from __future__ import annotations

from pathlib import Path

from .. import observability
from .base import (
    AgentResult,
    AgentStage,
    AgentTask,
    build_fresh_prompt,
    first_line,
    run_cli_jsonl,
)
from .config import AgentSettings


class CodexCliAgent:
    """Backend shelling out to the `codex` CLI (OpenAI Codex).

    Bound to one stage at construction time. Fresh runs use
    `codex exec --json ...`; resume uses `codex exec resume <thread_id> ...`
    — resume is a subcommand rather than a flag, so the command is assembled
    differently in each branch.
    """

    name = "codex_cli"

    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings
        self.stage: AgentStage = settings.stage
        self._sessions: dict[int, str] = {}

    def apply(
        self,
        task: AgentTask,
        worktree: Path,
        input: str = "",
    ) -> AgentResult:
        resume_id = self.get_session_id(task)
        if resume_id is None:
            prompt = build_fresh_prompt(self.stage, task, input)
            cmd = self._fresh_cmd(worktree, prompt)
        else:
            prompt = input
            cmd = self._resume_cmd(worktree, resume_id, prompt)

        with observability.track_generation(
            name="llm.codex_cli",
            model=self._settings.model or None,
            input=prompt,
        ) as gen:
            events = run_cli_jsonl(cmd, cwd=worktree, timeout_sec=self._settings.timeout_sec)

            new_session_id = self._extract_session_id(events)
            if new_session_id:
                self._sessions[task.id] = new_session_id

            response = self._extract_final_text(events)
            usage = self._extract_usage(events)
            observability.update_generation(gen, output=response, usage=usage)

        return AgentResult(
            stage=self.stage,
            response=response,
            result=first_line(response),
        )

    def get_session_id(self, task: AgentTask) -> str | None:
        return self._sessions.get(task.id)

    def _base_flags(self, worktree: Path) -> list[str]:
        flags = [
            "--json",
            "--full-auto",
            "--skip-git-repo-check",
            "-C",
            str(worktree),
        ]
        if self._settings.model:
            flags += ["-m", self._settings.model]
        return flags

    def _fresh_cmd(self, worktree: Path, prompt: str) -> list[str]:
        return ["codex", "exec", *self._base_flags(worktree), prompt]

    def _resume_cmd(self, worktree: Path, session_id: str, prompt: str) -> list[str]:
        return [
            "codex", "exec", "resume",
            *self._base_flags(worktree),
            session_id,
            prompt,
        ]

    @staticmethod
    def _extract_session_id(events: list[dict]) -> str | None:
        for event in events:
            if event.get("type") == "thread.started" and event.get("thread_id"):
                return str(event["thread_id"])
        return None

    @staticmethod
    def _extract_final_text(events: list[dict]) -> str:
        for event in reversed(events):
            if event.get("type") != "item.completed":
                continue
            item = event.get("item") or {}
            if item.get("type") == "agent_message" and "text" in item:
                return str(item["text"])
        return ""

    @staticmethod
    def _extract_usage(events: list[dict]) -> dict[str, int] | None:
        """Sum token counts across all `turn.completed` events.

        Codex emits a `turn.completed` event per turn with a `usage` dict:
        `{"input_tokens": ..., "output_tokens": ..., "cached_input_tokens": ...}`.
        Multi-turn runs get summed; single-turn just returns that one set.
        """
        totals: dict[str, int] = {}
        for event in events:
            if event.get("type") != "turn.completed":
                continue
            usage = event.get("usage") or {}
            if not isinstance(usage, dict):
                continue
            for key_src, key_dst in (
                ("input_tokens", "input"),
                ("output_tokens", "output"),
                ("cached_input_tokens", "cache_read_input"),
            ):
                if key_src in usage:
                    totals[key_dst] = totals.get(key_dst, 0) + int(usage[key_src])
        return totals or None
