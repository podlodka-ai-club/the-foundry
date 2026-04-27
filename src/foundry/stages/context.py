from __future__ import annotations

from pathlib import Path

from ..config import Settings
from ..models import Task

EXCLUDED_DIRS = frozenset({
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
})


def _collect_files(worktree: Path) -> list[str]:
    """Все обычные файлы worktree кроме служебных каталогов и aider-метаданных."""
    files: list[str] = []
    for path in sorted(worktree.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(worktree)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if rel.name.startswith(".aider"):
            continue
        files.append(str(rel))
    return files


def run(task: Task, settings: Settings) -> dict:
    """Готовит aider-payload: текст задания и список файлов worktree.

    Контракт сохраняется (`run(task, settings) -> dict`), pipeline передаёт
    `task` уже с проставленным `worktree_path` после `worktree.create_worktree`.
    """
    if not task.worktree_path:
        raise RuntimeError("task.worktree_path is not set; CONTEXT must run after worktree creation")
    worktree = Path(task.worktree_path)

    body = task.issue_body.strip()
    task_text = f"# {task.issue_title}\n\n{body}" if body else f"# {task.issue_title}"

    return {
        "task_text": task_text,
        "files": _collect_files(worktree),
        "worktree_path": str(worktree),
    }
