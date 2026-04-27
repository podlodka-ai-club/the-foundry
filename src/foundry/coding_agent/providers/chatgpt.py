from __future__ import annotations

from pathlib import Path

from .base import BaseLLMProvider


class ChatGPTProvider(BaseLLMProvider):
    DEFAULT_MODEL = "gpt-4"

    def configure_aider_command(
        self,
        base_cmd: list[str],
        env: dict[str, str],
    ) -> tuple[list[str], dict[str, str]]:
        cmd = base_cmd.copy()
        cmd.extend(["--model", self.get_model_name()])
        env_copy = env.copy()
        env_copy["OPENAI_API_KEY"] = self.api_key
        return cmd, env_copy

    def post_process_files(self, code_dir: Path) -> list[tuple[str, str]]:
        return []
