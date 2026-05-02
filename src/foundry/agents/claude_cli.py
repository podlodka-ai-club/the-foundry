from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import observability
from ..events import record_event
from .base import (
    AgentResult,
    AgentStage,
    AgentTask,
    build_fresh_prompt,
    first_line,
)
from .config import AgentSettings
from .context import get_parent_event_seq
from .streaming import _normalize_tool_event, iter_cli_jsonl


class ClaudeCliAgent:
    """Backend shelling out to the `claude` CLI (Anthropic subscription OAuth).

    Bound to one stage at construction time. Session state is private,
    keyed by task id: first call for a given task renders the prompt
    template from `prompts/<stage>.md`; subsequent calls pass
    `--resume <id>` with just `input`.

    Events are streamed line-by-line via `iter_cli_jsonl` and mirrored into
    `run_events` (`agent_tool` / `agent_text` / `agent_thinking` /
    `agent_result`) so the UI can watch a stage as it runs. The
    `AgentResult` contract is unchanged — streaming is purely a side
    channel.
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
            "--dangerously-skip-permissions",
            "--max-turns",
            str(self._settings.max_turns),
        ]
        if self._settings.model:
            cmd += ["--model", self._settings.model]
        if self._settings.mcp_config is not None:
            cmd += ["--mcp-config", str(self._settings.mcp_config)]
        if resume_id:
            cmd += ["--resume", resume_id]

        with observability.track_generation(
            name="llm.claude_cli",
            model=self._settings.model or None,
            input=prompt,
        ) as gen:
            events: list[dict[str, Any]] = []
            for event in iter_cli_jsonl(cmd, cwd=worktree):
                events.append(event)
                self._emit_for(task, event)

            new_session_id = self._extract_session_id(events)
            if new_session_id:
                self._sessions[task.id] = new_session_id

            response = self._extract_final_text(events)
            usage = self._extract_usage(events)
            cost_usd = self._extract_cost_usd(events)
            actual_model = self._extract_model(events) or self._settings.model or None
            observability.update_generation(
                gen, output=response, usage=usage, model=actual_model
            )

            # Final agent_result breadcrumb — summary (first line) for a
            # compact row in the event stream, and `text` (full response) so
            # the UI can render a collapsible "show full answer" block.
            self._record(
                task,
                kind="agent_result",
                payload={"summary": first_line(response), "text": response},
            )

        return AgentResult(
            stage=self.stage,
            response=response,
            result=first_line(response),
            cost_usd=cost_usd,
            tokens_in=(usage or {}).get("input") if usage else None,
            tokens_out=(usage or {}).get("output") if usage else None,
        )

    def get_session_id(self, task: AgentTask) -> str | None:
        cached = self._sessions.get(task.id)
        if cached is not None:
            return cached
        return self._settings.resume_session_id

    def _emit_for(self, task: AgentTask, event: dict[str, Any]) -> None:
        """Translate one streamed CLI event into `run_events` rows."""
        etype = event.get("type")
        if etype != "assistant":
            return
        message = event.get("message") or {}
        content = message.get("content") or []
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "tool_use":
                self._record(task, kind="agent_tool", payload=_normalize_tool_event(block))
            elif btype == "text":
                text = block.get("text")
                if text:
                    self._record(task, kind="agent_text", payload={"text": str(text)})
            elif btype == "thinking":
                # Claude CLI historically used `thinking` but some versions
                # emit the text under `text` — fall back to either.
                text = block.get("thinking") or block.get("text")
                if text:
                    self._record(task, kind="agent_thinking", payload={"text": str(text)})

    def _record(self, task: AgentTask, *, kind: str, payload: dict[str, Any]) -> None:
        """Persist an event iff we have a db to write to and a task id.

        When invoked from a sub-agent context (see `agent_event_context`),
        events nest under the framing `agent_call_started` event via
        `parent_event_seq`.
        """
        if self._settings.db_path is None or task.id is None:
            return
        record_event(
            self._settings.db_path,
            run_id=task.id,
            stage=self.stage.value,
            kind=kind,
            payload=payload,
            parent_event_seq=get_parent_event_seq(),
        )

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
    def _extract_cost_usd(events: list[dict]) -> float | None:
        """Pull `total_cost_usd` from the final `result` event, if present."""
        for event in reversed(events):
            if event.get("type") != "result":
                continue
            cost = event.get("total_cost_usd")
            if cost is None:
                return None
            try:
                return float(cost)
            except (TypeError, ValueError):
                return None
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
