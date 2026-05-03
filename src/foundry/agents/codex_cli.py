from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import observability, state
from ..events import record_event
from ..security import scrubbed_agent_env
from .base import (
    AgentResult,
    AgentStage,
    AgentTask,
    build_fresh_prompt,
    first_line,
)
from .config import AgentSettings
from .streaming import _normalize_tool_event, iter_cli_jsonl_with_retry


class CodexCliAgent:
    """Backend shelling out to the `codex` CLI (OpenAI Codex).

    Bound to one stage at construction time. Fresh runs use
    `codex exec --json ...`; resume uses `codex exec resume <thread_id> ...`
    — resume is a subcommand rather than a flag, so the command is assembled
    differently in each branch.

    Events are streamed line-by-line via `iter_cli_jsonl` and mirrored into
    `task_events` (`agent_tool` / `agent_text` / `agent_thinking` /
    `agent_result`) so the UI can watch a stage as it runs. Codex uses
    `item.completed` events rather than Claude's assistant content blocks, so
    this adapter normalizes completed items into the shared UI event shape.
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
            events = iter_cli_jsonl_with_retry(
                cmd,
                cwd=worktree,
                env=scrubbed_agent_env(self.name),
            )
            for event in events:
                self._emit_for(task, event)

            new_session_id = self._extract_session_id(events)
            if new_session_id:
                self._sessions[task.id] = new_session_id
                if self._settings.db_path is not None:
                    state.save_agent_session(
                        self._settings.db_path,
                        task.id,
                        self.stage.value,
                        self.name,
                        new_session_id,
                    )

            response = self._extract_final_text(events)
            usage = self._extract_usage(events)
            observability.update_generation(gen, output=response, usage=usage)

            self._record(
                task,
                kind="agent_result",
                payload={"summary": first_line(response), "text": response},
            )

        return AgentResult(
            stage=self.stage,
            response=response,
            result=first_line(response),
            tokens_in=(usage or {}).get("input") if usage else None,
            tokens_out=(usage or {}).get("output") if usage else None,
        )

    def get_session_id(self, task: AgentTask) -> str | None:
        if task.id in self._sessions:
            return self._sessions[task.id]
        if self._settings.db_path is None:
            return None
        session_id = state.get_agent_session(
            self._settings.db_path, task.id, self.stage.value, self.name
        )
        if session_id:
            self._sessions[task.id] = session_id
        return session_id

    def _base_flags(self, worktree: Path) -> list[str]:
        flags = [
            "--json",
            "--skip-git-repo-check",
            "-C",
            str(worktree),
        ]
        if not self._settings.safe_agent_mode:
            flags.insert(1, "--dangerously-bypass-approvals-and-sandbox")
        elif self._settings.sandbox_mode:
            flags += ["--sandbox", self._settings.sandbox_mode]
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

    def _emit_for(self, task: AgentTask, event: dict[str, Any]) -> None:
        """Translate one streamed Codex CLI event into `task_events` rows."""
        if event.get("type") != "item.completed":
            return
        item = event.get("item") or {}
        if not isinstance(item, dict):
            return

        item_type = item.get("type")
        if item_type == "agent_message":
            text = item.get("text")
            if text:
                self._record(task, kind="agent_text", payload={"text": str(text)})
            return

        if item_type in {"reasoning", "thought", "thinking"}:
            text = self._extract_item_text(item)
            if text:
                self._record(task, kind="agent_thinking", payload={"text": text})
            return

        if item_type in {"tool_call", "function_call", "local_shell_call"}:
            self._record(
                task,
                kind="agent_tool",
                payload=_normalize_tool_event(self._codex_tool_item_to_raw(item)),
            )

    def _record(self, task: AgentTask, *, kind: str, payload: dict[str, Any]) -> None:
        """Persist an event iff we have a db to write to and a task id."""
        if self._settings.db_path is None or task.id is None:
            return
        record_event(
            self._settings.db_path,
            task_id=task.id,
            stage=self.stage.value,
            kind=kind,
            payload=payload,
        )

    @staticmethod
    def _codex_tool_item_to_raw(item: dict[str, Any]) -> dict[str, Any]:
        """Adapt a Codex completed tool item to the shared tool normalizer."""
        raw_name = (
            item.get("name")
            or item.get("tool")
            or item.get("tool_name")
            or item.get("command")
            or item.get("type")
            or "tool"
        )
        name = CodexCliAgent._normalize_codex_tool_name(str(raw_name))
        tool_input = (
            item.get("input")
            or item.get("arguments")
            or item.get("args")
            or item.get("params")
            or item.get("action")
        )
        tool_input = CodexCliAgent._normalize_codex_tool_input(tool_input)
        if tool_input is None:
            tool_input = {
                key: value
                for key, value in item.items()
                if key not in {"id", "type", "name", "tool", "tool_name", "status"}
            } or None

        return {"name": name, "input": tool_input}

    @staticmethod
    def _normalize_codex_tool_name(name: str) -> str:
        if name in {"local_shell_call", "shell", "exec_command"}:
            return "Bash"
        return name

    @staticmethod
    def _normalize_codex_tool_input(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                return {"command": value}
            if isinstance(decoded, dict):
                return decoded
            return {"command": value}
        return None

    @staticmethod
    def _extract_item_text(item: dict[str, Any]) -> str:
        for key in ("text", "summary", "content", "message"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, list):
                parts = [str(part) for part in value if isinstance(part, str) and part]
                if parts:
                    return "\n".join(parts)
        return ""

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
