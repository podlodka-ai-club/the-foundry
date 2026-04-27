from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from foundry.coding_agent.providers import (
    AnthropicProvider,
    ChatGPTProvider,
    DeepSeekProvider,
    LLMProviderFactory,
)
from foundry.config import Settings


def _settings(**overrides) -> Settings:
    base = dict(
        source_repo="owner/sandbox",
        target_repo="owner/sandbox",
        issue_label="agent-task",
        worktree_root=Path("/tmp/wt"),
        db_path=Path("/tmp/db.sqlite"),
        poll_interval_seconds=30,
        coding_llm="DEEPSEEK",
    )
    base.update(overrides)
    return Settings(**base)


class TestDeepSeekProvider:
    def test_default_model_name(self) -> None:
        provider = DeepSeekProvider(api_key="test")
        assert provider.get_model_name() == "deepseek/deepseek-chat"

    def test_custom_model_name(self) -> None:
        provider = DeepSeekProvider(api_key="test", model_name="deepseek/custom")
        assert provider.get_model_name() == "deepseek/custom"

    def test_configure_aider_command(self) -> None:
        provider = DeepSeekProvider(api_key="sk-test")
        cmd, env = provider.configure_aider_command(["aider", "--yes-always"], {})
        assert "--model" in cmd and "deepseek/deepseek-chat" in cmd
        assert env["DEEPSEEK_API_KEY"] == "sk-test"

    def test_post_process_renames_malformed_filename(self) -> None:
        provider = DeepSeekProvider(api_key="x")
        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = Path(tmpdir)
            (code_dir / "Let's do it.test.py").write_text("print('test')")
            renamed = provider.post_process_files(code_dir)
            assert renamed == [("Let's do it.test.py", "test.py")]
            assert (code_dir / "test.py").exists()

    def test_post_process_renames_malformed_directory(self) -> None:
        provider = DeepSeekProvider(api_key="x")
        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = Path(tmpdir)
            bad_dir = code_dir / "Let's produce the SEARCH"
            bad_dir.mkdir()
            (bad_dir / "REPLACE block.script.py").write_text("print('hi')")
            renamed = provider.post_process_files(code_dir)
            assert len(renamed) == 1
            assert renamed[0][1] == "script.py"
            assert (code_dir / "script.py").exists()
            assert not bad_dir.exists()

    def test_post_process_keeps_correct_filename(self) -> None:
        provider = DeepSeekProvider(api_key="x")
        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = Path(tmpdir)
            (code_dir / "hello.py").write_text("print('hi')")
            renamed = provider.post_process_files(code_dir)
            assert renamed == []


class TestAnthropicProvider:
    def test_default_model_name(self) -> None:
        provider = AnthropicProvider(api_key="test")
        assert provider.get_model_name() == "claude-3-5-sonnet-20241022"

    def test_custom_model_name(self) -> None:
        provider = AnthropicProvider(api_key="test", model_name="claude-custom")
        assert provider.get_model_name() == "claude-custom"

    def test_configure_aider_command(self) -> None:
        provider = AnthropicProvider(api_key="sk-test")
        cmd, env = provider.configure_aider_command(["aider"], {})
        assert "claude-3-5-sonnet-20241022" in cmd
        assert env["ANTHROPIC_API_KEY"] == "sk-test"

    def test_post_process_files_returns_empty(self) -> None:
        provider = AnthropicProvider(api_key="x")
        with tempfile.TemporaryDirectory() as tmpdir:
            assert provider.post_process_files(Path(tmpdir)) == []


class TestChatGPTProvider:
    def test_default_model_name(self) -> None:
        provider = ChatGPTProvider(api_key="test")
        assert provider.get_model_name() == "gpt-4"

    def test_custom_model_name(self) -> None:
        provider = ChatGPTProvider(api_key="test", model_name="gpt-4-turbo")
        assert provider.get_model_name() == "gpt-4-turbo"

    def test_configure_aider_command(self) -> None:
        provider = ChatGPTProvider(api_key="sk-test")
        cmd, env = provider.configure_aider_command(["aider"], {})
        assert "gpt-4" in cmd
        assert env["OPENAI_API_KEY"] == "sk-test"


class TestLLMProviderFactory:
    def test_create_provider_deepseek(self) -> None:
        provider = LLMProviderFactory.create_provider("DEEPSEEK", "key")
        assert isinstance(provider, DeepSeekProvider)
        assert provider.api_key == "key"

    def test_create_provider_anthropic(self) -> None:
        provider = LLMProviderFactory.create_provider("ANTHROPIC", "key")
        assert isinstance(provider, AnthropicProvider)

    def test_create_provider_chatgpt(self) -> None:
        provider = LLMProviderFactory.create_provider("CHATGPT", "key")
        assert isinstance(provider, ChatGPTProvider)

    def test_create_provider_invalid_type(self) -> None:
        with pytest.raises(ValueError, match="Unsupported LLM type"):
            LLMProviderFactory.create_provider("GEMINI", "key")

    def test_create_from_settings_uses_active_provider(self) -> None:
        settings = _settings(coding_llm="ANTHROPIC", anthropic_api_key="sk-a")
        provider = LLMProviderFactory.create_from_settings(settings)
        assert isinstance(provider, AnthropicProvider)
        assert provider.api_key == "sk-a"

    def test_create_from_settings_uses_model_override(self) -> None:
        settings = _settings(
            coding_llm="DEEPSEEK",
            deepseek_api_key="sk-d",
            deepseek_model_name="deepseek/special",
        )
        provider = LLMProviderFactory.create_from_settings(settings)
        assert provider.get_model_name() == "deepseek/special"

    def test_create_from_settings_raises_without_key(self) -> None:
        settings = _settings(coding_llm="DEEPSEEK", deepseek_api_key=None)
        with pytest.raises(ValueError, match="API key"):
            LLMProviderFactory.create_from_settings(settings)

    def test_get_supported_providers(self) -> None:
        supported = LLMProviderFactory.get_supported_providers()
        assert {"DEEPSEEK", "ANTHROPIC", "CHATGPT"} <= set(supported)
