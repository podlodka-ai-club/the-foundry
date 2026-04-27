from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseLLMProvider(ABC):
    """Базовый интерфейс для LLM-провайдеров aider."""

    DEFAULT_MODEL: str = ""

    def __init__(self, api_key: str, model_name: str | None = None) -> None:
        self.api_key = api_key
        self._model_name = model_name or self.DEFAULT_MODEL

    def get_model_name(self) -> str:
        return self._model_name

    @abstractmethod
    def configure_aider_command(
        self,
        base_cmd: list[str],
        env: dict[str, str],
    ) -> tuple[list[str], dict[str, str]]:
        """Добавляет провайдер-специфичные параметры aider и env."""

    @abstractmethod
    def post_process_files(self, code_dir: Path) -> list[tuple[str, str]]:
        """Опциональная пост-обработка файлов после прогона aider."""

    def get_provider_name(self) -> str:
        return self.__class__.__name__.replace("Provider", "")
