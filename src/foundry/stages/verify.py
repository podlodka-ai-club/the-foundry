from __future__ import annotations

from pathlib import Path

from langfuse import observe

from .. import shell
from ..config import Settings
from ..models import Task


@observe(name="stage.verify")
def run(
    task: Task,
    worktree_path: Path,
    settings: Settings,
    impl_result: dict | None = None,
) -> dict:
    """STUB: runs `echo ok` in the worktree. Day 5 replaces with pytest/ruff/etc.

    Until a real verifier exists, the implement agent's own response is carried
    through as `report` so the PR body can show a human-readable explanation of
    what was done.
    """
    result = shell.run(["echo", "ok"], cwd=worktree_path)
    report = ""
    if impl_result:
        report = impl_result.get("response") or impl_result.get("result") or ""
    return {
        "passed": result.ok,
        "stdout": result.stdout.strip(),
        "report": report,
    }
