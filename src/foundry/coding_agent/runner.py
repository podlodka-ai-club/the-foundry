from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import structlog

from .providers.base import BaseLLMProvider

log = structlog.get_logger()


@dataclass(frozen=True)
class AiderResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


def run_aider(
    *,
    worktree_path: Path,
    task_text: str,
    files: list[str],
    provider: BaseLLMProvider,
    timeout_seconds: int = 600,
) -> AiderResult:
    """Запускает aider в указанном worktree с заданным провайдером.

    Aider вызывается с ``--yes-always --no-git``: сам автоконфирмит изменения,
    но git-операции остаются за PR-стадией pipeline.
    """
    if not worktree_path.exists():
        raise FileNotFoundError(f"worktree not found: {worktree_path}")

    base_cmd = ["aider", "--yes-always", "--no-git"]
    cmd, env = provider.configure_aider_command(base_cmd, os.environ.copy())
    for file in files:
        cmd.extend(["--file", file])
    cmd.extend(["--message", task_text])

    log.info(
        "aider.start",
        provider=provider.get_provider_name(),
        model=provider.get_model_name(),
        worktree=str(worktree_path),
        files=len(files),
        timeout=timeout_seconds,
    )

    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            cwd=worktree_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        log.warning("aider.timeout", duration=duration, timeout=timeout_seconds)
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return AiderResult(
            ok=False,
            returncode=-1,
            stdout=stdout,
            stderr=stderr or f"aider timed out after {timeout_seconds}s",
            duration_seconds=duration,
        )

    duration = time.monotonic() - started
    log.info(
        "aider.done",
        returncode=completed.returncode,
        duration=duration,
    )
    return AiderResult(
        ok=completed.returncode == 0,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        duration_seconds=duration,
    )
