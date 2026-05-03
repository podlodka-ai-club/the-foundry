from __future__ import annotations

import io
from typing import Any

import pytest

from foundry.agents.streaming import (
    CliProcessError,
    _normalize_tool_event,
    iter_cli_jsonl,
)


class _FakePopen:
    """Stand-in for subprocess.Popen that serves pre-baked stdout lines."""

    def __init__(self, lines: list[str], returncode: int = 0, stderr: str = "") -> None:
        self.stdout = io.StringIO("".join(lines))
        self.stderr = io.StringIO(stderr)
        self._returncode = returncode

    # subprocess.Popen-compatible surface used by iter_cli_jsonl.
    def wait(self) -> int:
        return self._returncode


def _install_fake_popen(monkeypatch: pytest.MonkeyPatch, popen_obj: _FakePopen) -> None:
    def factory(*_args: Any, **_kwargs: Any) -> _FakePopen:
        return popen_obj

    monkeypatch.setattr("foundry.agents.streaming.subprocess.Popen", factory)


def test_iter_cli_jsonl_streams_and_parses_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    lines = [
        '{"type": "system", "session_id": "s1"}\n',
        '{"type": "assistant", "message": {"content": []}}\n',
        '{"type": "result", "result": "ok"}\n',
    ]
    _install_fake_popen(monkeypatch, _FakePopen(lines))

    # Act
    got = list(iter_cli_jsonl(["fake"]))

    # Assert
    assert len(got) == 3
    assert got[0]["type"] == "system"
    assert got[0]["session_id"] == "s1"
    assert got[2]["result"] == "ok"


def test_iter_cli_jsonl_skips_invalid_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: garbage + empty line between two valid JSON events.
    lines = [
        '{"type": "a"}\n',
        "not json at all\n",
        "\n",
        '{"type": "b"}\n',
    ]
    _install_fake_popen(monkeypatch, _FakePopen(lines))

    # Act
    got = list(iter_cli_jsonl(["fake"]))

    # Assert
    assert [e["type"] for e in got] == ["a", "b"]


def test_iter_cli_jsonl_raises_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = ['{"type": "a"}\n']
    _install_fake_popen(monkeypatch, _FakePopen(lines, returncode=1, stderr="boom"))

    with pytest.raises(CliProcessError, match="fake exited with code 1: boom") as exc:
        list(iter_cli_jsonl(["fake"]))

    assert exc.value.returncode == 1
    assert exc.value.stderr == "boom"


def test_normalize_tool_event_read_uses_file_path() -> None:
    out = _normalize_tool_event({"name": "Read", "input": {"file_path": "/foo.py"}})

    assert out["tool"] == "Read"
    assert out["detail"] == "/foo.py"
    assert out["args"] == {"file_path": "/foo.py"}


def test_normalize_tool_event_bash_uses_description() -> None:
    out = _normalize_tool_event(
        {"name": "Bash", "input": {"description": "run tests", "command": "pytest"}}
    )

    assert out["tool"] == "Bash"
    assert out["detail"] == "run tests"


def test_normalize_tool_event_bash_falls_back_to_command() -> None:
    out = _normalize_tool_event({"name": "Bash", "input": {"command": "pytest -q"}})

    assert out["detail"] == "pytest -q"


def test_normalize_tool_event_grep_uses_pattern() -> None:
    out = _normalize_tool_event({"name": "Grep", "input": {"pattern": "foo.*"}})

    assert out["detail"] == "foo.*"


def test_normalize_tool_event_unknown_tool_has_no_detail() -> None:
    out = _normalize_tool_event({"name": "FooBar", "input": {"x": 1}})

    assert out["tool"] == "FooBar"
    assert out["detail"] is None
    assert out["args"] == {"x": 1}


def test_normalize_tool_event_todowrite_counts() -> None:
    out = _normalize_tool_event(
        {"name": "TodoWrite", "input": {"todos": [{"t": 1}, {"t": 2}, {"t": 3}]}}
    )

    assert out["detail"] == "3 todos"


def test_normalize_tool_event_truncates_long_detail() -> None:
    long_path = "/" + "a" * 500
    out = _normalize_tool_event({"name": "Read", "input": {"file_path": long_path}})

    assert out["detail"] is not None
    assert len(out["detail"]) <= 100
    assert out["detail"].endswith("…")


def test_normalize_tool_event_missing_input_is_safe() -> None:
    out = _normalize_tool_event({"name": "Read"})

    assert out["tool"] == "Read"
    assert out["detail"] is None
    assert out["args"] is None
