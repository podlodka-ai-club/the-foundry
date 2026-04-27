from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class ShellError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, stdout: str, stderr: str):
        super().__init__(
            f"Command failed ({returncode}): {' '.join(cmd)}\nstdout: {stdout}\nstderr: {stderr}"
        )
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = True,
    timeout: int = 120,
    env: dict | None = None,
) -> Result:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    result = Result(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and not result.ok:
        raise ShellError(cmd, result.returncode, result.stdout, result.stderr)
    return result
