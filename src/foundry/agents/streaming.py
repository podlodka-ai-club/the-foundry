from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Iterator

import structlog

log = structlog.get_logger(__name__)

_RATE_LIMIT_SIGNALS = (
    "rate limit",
    "rate_limit",
    "429",
    "529",
    "too many requests",
    "overloaded",
    "capacity",
)
_RETRY_DELAYS = (30, 60, 120)  # seconds between attempts

MAX_TOOL_DETAIL_LEN = 100


class CliProcessError(RuntimeError):
    """Raised when a streamed CLI process exits unsuccessfully."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str = "") -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        cmd_name = cmd[0] if cmd else "<unknown>"
        detail = stderr.strip()
        message = f"{cmd_name} exited with code {returncode}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)

# Per-tool mapping: which key in tool `input` carries a short human-readable
# detail. Kept in sync with the reference parser in myagent's telegram_ui.
_TOOL_DETAIL_KEYS: dict[str, tuple[str, ...]] = {
    "Read": ("file_path",),
    "Edit": ("file_path",),
    "Write": ("file_path",),
    "NotebookEdit": ("notebook_path", "file_path"),
    "Bash": ("description", "command"),
    "Grep": ("pattern",),
    "Glob": ("pattern",),
    "Task": ("description",),
    "WebFetch": ("url",),
    "WebSearch": ("query",),
    "Skill": ("skill", "name"),
    "SlashCommand": ("command", "name"),
    # TodoWrite is special-cased (count of todos) — no key lookup.
    "TodoWrite": (),
}


def _is_rate_limit_error(err: CliProcessError) -> bool:
    text = err.stderr.lower()
    return any(signal in text for signal in _RATE_LIMIT_SIGNALS)


def iter_cli_jsonl_with_retry(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Run a streaming CLI command with rate-limit retry.

    Unlike `iter_cli_jsonl`, collects all events into a list so the caller
    gets a complete, consistent result even after a retry. Retries up to
    ``len(_RETRY_DELAYS)`` times with exponential back-off when the process
    exits with a rate-limit signal in stderr.
    """
    last_err: CliProcessError | None = None
    for attempt, delay in enumerate(
        [0] + list(_RETRY_DELAYS), start=1
    ):
        if delay:
            log.warning(
                "streaming.rate_limit_retry",
                attempt=attempt,
                delay_sec=delay,
                cmd=cmd[0] if cmd else "",
            )
            time.sleep(delay)
        try:
            return list(iter_cli_jsonl(cmd, cwd=cwd, env=env))
        except CliProcessError as exc:
            if _is_rate_limit_error(exc):
                last_err = exc
                continue
            raise
    raise last_err  # type: ignore[misc]


def iter_cli_jsonl(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream newline-delimited JSON events from a subprocess stdout.

    Yields parsed dicts line-by-line as the process writes them. Invalid /
    empty lines are logged at warning level and skipped — never raises on
    parse failure.

    On process exit: stderr is drained and non-zero exits raise
    `CliProcessError`; subprocess-level failures (spawn error, etc.) propagate
    to the caller. This keeps agent failures from being mistaken for a clean
    empty response by the workflow.
    """
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # line-buffered
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                log.warning(
                    "streaming.jsonl.parse_failed",
                    error=str(exc),
                    line_preview=stripped[:200],
                )
                continue
    finally:
        # Ensure process is reaped and stderr is drained no matter how the
        # iterator is closed (normal exhaust, GeneratorExit, exception).
        returncode = proc.wait()
        stderr_text = ""
        if proc.stderr is not None:
            try:
                stderr_text = proc.stderr.read()
            except Exception:
                stderr_text = ""
        if returncode != 0:
            log.warning(
                "streaming.jsonl.nonzero_exit",
                cmd=cmd[0] if cmd else "",
                returncode=returncode,
                stderr=stderr_text[:2000],
            )
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()
        if returncode != 0:
            raise CliProcessError(cmd, returncode, stderr_text)


def _normalize_tool_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Turn a raw `tool_use` block into `{tool, detail?, args?}`.

    Pure function (no side effects). `raw` is the assistant-message block
    (e.g. `{"type": "tool_use", "name": "Read", "input": {...}}`).

    `detail` picks a short string out of `input` per tool-specific rules
    (see `_TOOL_DETAIL_KEYS`). Unknown tools get `detail=None`.
    """
    name = str(raw.get("name") or "tool")
    tool_input = raw.get("input")
    if not isinstance(tool_input, dict):
        tool_input = None

    detail = _extract_detail(name, tool_input)

    out: dict[str, Any] = {"tool": name, "detail": detail, "args": tool_input}
    return out


def _extract_detail(tool_name: str, tool_input: dict[str, Any] | None) -> str | None:
    if tool_name == "TodoWrite":
        todos = (tool_input or {}).get("todos")
        if isinstance(todos, list):
            return f"{len(todos)} todos"
        return None

    if not tool_input:
        return None

    keys = _TOOL_DETAIL_KEYS.get(tool_name)
    if keys is None:
        return None

    for key in keys:
        value = tool_input.get(key)
        if value:
            text = str(value).replace("\n", " ").strip()
            if len(text) > MAX_TOOL_DETAIL_LEN:
                text = text[: MAX_TOOL_DETAIL_LEN - 1] + "…"
            return text
    return None
