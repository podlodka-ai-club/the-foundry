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


class OpencodeCliAgent:
    """Backend shelling out to the `opencode` CLI.

    Bound to one stage at construction time. `opencode run --format json`
    emits NDJSON events; resume uses `--session <id>` on subsequent calls.
    Provider auth is supplied via env (e.g. `OPENROUTER_API_KEY`).

    TODO(PR3.5): stream events via `iter_cli_jsonl` and emit `agent_tool` /
    `agent_text` / `agent_result` into `run_events`. Opencode's NDJSON
    (`type:"text"` with `part.text`, separate tool events) doesn't match
    Claude's `assistant`-content-block shape — the tool-normalizer needs an
    opencode adapter. Deferred to keep this PR focused on claude_cli.
    """

    name = "opencode_cli"

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
            message = build_fresh_prompt(self.stage, task, input)
        else:
            message = input

        cmd: list[str] = [
            "opencode", "run",
            "--format", "json",
            "--dir", str(worktree),
        ]
        if self._settings.model:
            cmd += ["-m", self._settings.model]
        if resume_id:
            cmd += ["--session", resume_id]
        cmd.append(message)

        with observability.track_generation(
            name="llm.opencode_cli",
            model=self._settings.model or None,
            input=message,
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

    @staticmethod
    def _extract_session_id(events: list[dict]) -> str | None:
        for event in events:
            sid = event.get("sessionID") or (event.get("part") or {}).get("sessionID")
            if sid:
                return str(sid)
        return None

    @staticmethod
    def _extract_final_text(events: list[dict]) -> str:
        """Concatenate all assistant text chunks in order.

        opencode emits each text block as its own `type:"text"` event with the
        full chunk in `part.text`; the final response is the concatenation.
        """
        chunks: list[str] = []
        for event in events:
            if event.get("type") != "text":
                continue
            part = event.get("part") or {}
            text = part.get("text")
            if text:
                chunks.append(str(text))
        return "".join(chunks)

    @staticmethod
    def _extract_usage(events: list[dict]) -> dict[str, int] | None:
        """Pull token counts from whichever opencode event carries them.

        Field names vary by opencode version; checks several likely paths
        (top-level `tokens`, `metadata.tokens`, `part.tokens`, message
        metadata) and returns the first hit.
        """
        for event in reversed(events):
            tokens = (
                event.get("tokens")
                or (event.get("metadata") or {}).get("tokens")
                or (event.get("part") or {}).get("tokens")
                or (event.get("message") or {}).get("metadata", {}).get("tokens")
            )
            if not isinstance(tokens, dict) or not tokens:
                continue
            out: dict[str, int] = {}
            if "input" in tokens:
                out["input"] = int(tokens["input"])
            if "output" in tokens:
                out["output"] = int(tokens["output"])
            cache = tokens.get("cache")
            if isinstance(cache, dict):
                if "read" in cache:
                    out["cache_read_input"] = int(cache["read"])
                if "write" in cache:
                    out["cache_creation_input"] = int(cache["write"])
            return out or None
        return None
