from __future__ import annotations

import re
from pathlib import Path

from .base import BaseLLMProvider


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek-провайдер с пост-обработкой имён файлов.

    DeepSeek иногда возвращает имена файлов вида ``Let's do it.factorial.py`` —
    post_process_files их выправляет до ``factorial.py``.
    """

    DEFAULT_MODEL = "deepseek/deepseek-chat"

    def configure_aider_command(
        self,
        base_cmd: list[str],
        env: dict[str, str],
    ) -> tuple[list[str], dict[str, str]]:
        cmd = base_cmd.copy()
        cmd.extend(["--model", self.get_model_name()])
        env_copy = env.copy()
        env_copy["DEEPSEEK_API_KEY"] = self.api_key
        return cmd, env_copy

    def post_process_files(self, code_dir: Path) -> list[tuple[str, str]]:
        renamed: list[tuple[str, str]] = []

        def extract_correct_name(name: str) -> str:
            match = re.search(r"([a-zA-Z0-9_-]+\.[a-zA-Z0-9]+)$", name)
            if match:
                return match.group(1)
            parts = name.split(".")
            if len(parts) >= 2:
                return ".".join(parts[-2:])
            return name

        def is_malformed(name: str) -> bool:
            bad_patterns = (
                "Let's ",
                "SEARCH/REPLACE",
                "REPLACE block",
                "produce the",
                "craft the",
            )
            if any(p in name for p in bad_patterns):
                return True
            if " " in name and not name.startswith("."):
                return True
            return False

        for item in code_dir.iterdir():
            item_name = item.name
            if item_name.startswith("."):
                continue
            if not is_malformed(item_name):
                continue
            try:
                if item.is_dir():
                    for nested in item.iterdir():
                        correct = extract_correct_name(nested.name)
                        nested.rename(code_dir / correct)
                        renamed.append((f"{item_name}/{nested.name}", correct))
                    item.rmdir()
                else:
                    correct = extract_correct_name(item_name)
                    if correct != item_name:
                        item.rename(code_dir / correct)
                        renamed.append((item_name, correct))
            except OSError:
                # Не падаем, если переименование не удалось — это just-in-case-fix.
                continue

        return renamed
