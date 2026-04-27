from __future__ import annotations

from ..config import Settings
from ..models import Task


def run(task: Task, ctx: dict, settings: Settings) -> dict:
    """Passthrough-планировщик: aider сам планирует и применяет изменения.

    Возвращает один шаг ``aider_run``, который IMPLEMENT передаст в run_aider.
    Если позже захотим делать отдельный LLM-вызов для разбиения задачи —
    место для этого здесь.
    """
    return {
        "steps": [
            {
                "kind": "aider_run",
                "task_text": ctx["task_text"],
                "files": ctx["files"],
            }
        ]
    }
