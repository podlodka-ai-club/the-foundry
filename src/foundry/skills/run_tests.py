from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path


def run_tests_impl(*, command: str | None = None) -> dict:
    """Execute tests in FOUNDRY_WORKTREE, return structured result."""
    worktree = os.environ.get("FOUNDRY_WORKTREE")
    if not worktree:
        return {
            "ok": False,
            "error": "FOUNDRY_WORKTREE not set",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_sec": 0.0,
        }
    cwd = Path(worktree)
    cmd_str = command or os.environ.get("FOUNDRY_TEST_COMMAND") or "pytest -x -q"
    timeout_sec = int(os.environ.get("FOUNDRY_TEST_TIMEOUT_SEC", "600"))
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            shlex.split(cmd_str),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as e:
        return {
            "ok": False,
            "error": "timeout",
            "stdout": (e.stdout or "")[-16000:],
            "stderr": (e.stderr or "")[-16000:],
            "exit_code": -1,
            "duration_sec": time.monotonic() - t0,
        }
    return {
        "ok": proc.returncode == 0,
        "stdout": proc.stdout[-16000:],
        "stderr": proc.stderr[-16000:],
        "exit_code": proc.returncode,
        "duration_sec": time.monotonic() - t0,
    }


__all__ = ["run_tests_impl"]
