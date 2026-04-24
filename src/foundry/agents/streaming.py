from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Iterator

import structlog

log = structlog.get_logger(__name__)

MAX_TOOL_DETAIL_LEN = 100

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

    On process exit: stderr is drained and logged if the exit code is
    non-zero; pipes are closed. Subprocess-level failures (spawn error, etc.)
    propagate to the caller.
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
