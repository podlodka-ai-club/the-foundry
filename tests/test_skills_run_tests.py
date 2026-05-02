from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from foundry.skills.run_tests import run_tests_impl


def test_run_tests_no_worktree_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_WORKTREE", raising=False)

    out = run_tests_impl()

    assert out["ok"] is False
    assert "FOUNDRY_WORKTREE" in out["error"]
    assert out["exit_code"] == -1


def test_run_tests_zero_exit_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOUNDRY_WORKTREE", str(tmp_path))

    fake = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
    with patch("foundry.skills.run_tests.subprocess.run", return_value=fake):
        out = run_tests_impl()

    assert out["ok"] is True
    assert out["exit_code"] == 0
    assert out["stdout"] == "ok"


def test_run_tests_nonzero_exit_not_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOUNDRY_WORKTREE", str(tmp_path))

    fake = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")
    with patch("foundry.skills.run_tests.subprocess.run", return_value=fake):
        out = run_tests_impl()

    assert out["ok"] is False
    assert out["exit_code"] == 1
    assert out["stderr"] == "boom"


def test_run_tests_command_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOUNDRY_WORKTREE", str(tmp_path))
    monkeypatch.setenv("FOUNDRY_TEST_COMMAND", "pytest -q")

    captured: dict = {}

    def _capture(args, **kwargs):
        captured["args"] = args
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch("foundry.skills.run_tests.subprocess.run", side_effect=_capture):
        run_tests_impl(command="ruff check .")

    assert captured["args"] == ["ruff", "check", "."]


def test_run_tests_truncates_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOUNDRY_WORKTREE", str(tmp_path))

    huge = "x" * 100_000
    fake = subprocess.CompletedProcess(args=[], returncode=0, stdout=huge, stderr="")
    with patch("foundry.skills.run_tests.subprocess.run", return_value=fake):
        out = run_tests_impl()

    assert len(out["stdout"]) == 16_000
    # Tail kept, not head.
    assert out["stdout"] == huge[-16_000:]


def test_run_tests_timeout_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOUNDRY_WORKTREE", str(tmp_path))

    def _raise(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1, output="partial", stderr="err")

    with patch("foundry.skills.run_tests.subprocess.run", side_effect=_raise):
        out = run_tests_impl()

    assert out["ok"] is False
    assert out["error"] == "timeout"
    assert out["exit_code"] == -1
    assert "partial" in out["stdout"]
    assert "err" in out["stderr"]
