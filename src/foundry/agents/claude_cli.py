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


class ClaudeCliAgent:
    """Backend shelling out to the `claude` CLI (Anthropic subscription OAuth).

    Bound to one stage at construction time. Session state is private,
    keyed by task id: first call for a given task renders the prompt
    template from `prompts/<stage>.md`; subsequent calls pass
    `--resume <id>` with just `input`.
    """

    name = "claude_cli"

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
        else:
            prompt = input

        cmd: list[str] = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "acceptEdits",
            "--max-turns",
            str(self._settings.max_turns),
        ]
        if self._settings.model:
            cmd += ["--model", self._settings.model]
        if resume_id:
            cmd += ["--resume", resume_id]

        with observability.track_generation(
            name="llm.claude_cli",
            model=self._settings.model or None,
            input=prompt,
        ) as gen:
            events = run_cli_jsonl(cmd, cwd=worktree, timeout_sec=self._settings.timeout_sec)

            new_session_id = self._extract_session_id(events)
            if new_session_id:
                self._sessions[task.id] = new_session_id

            response = self._extract_final_text(events)
            usage = self._extract_usage(events)
            actual_model = self._extract_model(events) or self._settings.model or None
            observability.update_generation(
                gen, output=response, usage=usage, model=actual_model
            )

        return AgentResult(
            stage=self.stage,
            response=response,
            result=first_line(response),
        )

    def get_session_id(self, task: AgentTask) -> str | None:
        return self._sessions.get(task.id)

    @staticmethod
    def _extract_session_id(events: list[dict]) -> str | None:
        for event in events:
            if event.get("type") == "system" and event.get("session_id"):
                return str(event["session_id"])
        return None

    @staticmethod
    def _extract_final_text(events: list[dict]) -> str:
        for event in reversed(events):
            if event.get("type") == "result" and "result" in event:
                return str(event["result"])
        for event in reversed(events):
            if event.get("type") == "assistant":
                message = event.get("message") or {}
                for block in message.get("content", []):
                    if block.get("type") == "text":
                        return str(block.get("text", ""))
        return ""

    @staticmethod
    def _extract_usage(events: list[dict]) -> dict[str, int] | None:
        """Pull token counts from the final `result` event's `usage` payload."""
        for event in reversed(events):
            if event.get("type") != "result":
                continue
            usage = event.get("usage") or {}
            if not isinstance(usage, dict) or not usage:
                continue
            out: dict[str, int] = {}
            if "input_tokens" in usage:
                out["input"] = int(usage["input_tokens"])
            if "output_tokens" in usage:
                out["output"] = int(usage["output_tokens"])
            if "cache_read_input_tokens" in usage:
                out["cache_read_input"] = int(usage["cache_read_input_tokens"])
            if "cache_creation_input_tokens" in usage:
                out["cache_creation_input"] = int(usage["cache_creation_input_tokens"])
            return out or None
        return None

    @staticmethod
    def _extract_model(events: list[dict]) -> str | None:
        """Read the fully-qualified model id from the `result` event.

        Claude exposes it via `modelUsage` — a dict keyed by model name
        (e.g. `claude-haiku-4-5-20251001`). Older versions had a top-level
        `model` field, which we still check as a fallback.
        """
        for event in reversed(events):
            if event.get("type") != "result":
                continue
            model_usage = event.get("modelUsage")
            if isinstance(model_usage, dict) and model_usage:
                return str(next(iter(model_usage)))
            if event.get("model"):
                return str(event["model"])
        return None
