from __future__ import annotations

from pathlib import Path

from ..coding_agent import LLMProviderFactory, run_aider
from ..config import Settings
from ..models import Task


def run(task: Task, plan: dict, worktree_path: Path, settings: Settings) -> dict:
    """Запускает aider в worktree через выбранного провайдера.

    Plan приходит из ``plan.run`` в формате ``{"steps": [{"kind": "aider_run", ...}]}``.
    Aider сам определяет contextual набор файлов и применяет изменения; git-операции
    остаются за PR-стадией (флаг ``--no-git``).
    """
    steps = plan.get("steps", [])
    if not steps:
        raise RuntimeError("implement: empty plan")
    step = steps[0]
    if step.get("kind") != "aider_run":
        raise RuntimeError(f"implement: unsupported step kind {step.get('kind')!r}")

    provider = LLMProviderFactory.create_from_settings(settings)
    result = run_aider(
        worktree_path=worktree_path,
        task_text=step["task_text"],
        files=step.get("files", []),
        provider=provider,
        timeout_seconds=settings.aider_timeout_seconds,
    )

    renamed = provider.post_process_files(worktree_path)

    if not result.ok:
        # Урезаем хвост вывода, чтобы поднять exception читаемого размера.
        tail = (result.stderr or result.stdout)[-2048:]
        raise RuntimeError(
            f"aider failed (rc={result.returncode}, provider={provider.get_provider_name()}): {tail}"
        )

    return {
        "ok": True,
        "provider": provider.get_provider_name(),
        "model": provider.get_model_name(),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-4096:],
        "renamed_files": renamed,
        "duration_seconds": result.duration_seconds,
    }
