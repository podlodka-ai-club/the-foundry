import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from agent.providers import (
    DeepSeekProvider,
    AnthropicProvider,
    ChatGPTProvider,
    LLMProviderFactory
)


class TestDeepSeekProvider:
    """Тесты для DeepSeekProvider."""
    
    def test_get_model_name_default(self):
        """Тест получения дефолтного названия модели."""
        with patch.dict(os.environ, {}, clear=True):
            provider = DeepSeekProvider(api_key="test_key")
            assert provider.get_model_name() == 'deepseek/deepseek-chat'
    
    def test_get_model_name_from_env(self):
        """Тест получения названия модели из конфига."""
        with patch.dict(os.environ, {'DEEPSEEK_MODEL_NAME': 'deepseek/custom-model'}):
            provider = DeepSeekProvider(api_key="test_key")
            assert provider.get_model_name() == 'deepseek/custom-model'
    
    def test_configure_aider_command(self):
        """Тест настройки команды aider."""
        provider = DeepSeekProvider(api_key="test_key")
        base_cmd = ['aider', '--yes-always']
        env = {}
        
        cmd, new_env = provider.configure_aider_command(base_cmd, env)
        
        assert '--model' in cmd
        assert 'deepseek/deepseek-chat' in cmd
        assert new_env['DEEPSEEK_API_KEY'] == 'test_key'
    
    def test_post_process_files_malformed_filename(self):
        """Тест пост-обработки файлов с неправильными именами."""
        provider = DeepSeekProvider(api_key="test_key")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = Path(tmpdir)
            
            malformed_file = code_dir / "Let's do it.test.py"
            malformed_file.write_text("print('test')")
            
            renamed = provider.post_process_files(code_dir)
            
            assert len(renamed) == 1
            assert renamed[0] == ("Let's do it.test.py", "test.py")
            assert (code_dir / "test.py").exists()
            assert not malformed_file.exists()
    
    def test_post_process_files_directory(self):
        """Тест пост-обработки директорий с неправильными именами."""
        provider = DeepSeekProvider(api_key="test_key")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = Path(tmpdir)
            
            bad_dir = code_dir / "Let's produce the SEARCH"
            bad_dir.mkdir()
            bad_file = bad_dir / "REPLACE block.script.py"
            bad_file.write_text("print('test')")
            
            renamed = provider.post_process_files(code_dir)
            
            assert len(renamed) == 1
            assert renamed[0][1] == "script.py"
            assert (code_dir / "script.py").exists()
            assert not bad_dir.exists()
    
    def test_post_process_files_correct_filename(self):
        """Тест пост-обработки файлов с правильными именами."""
        provider = DeepSeekProvider(api_key="test_key")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = Path(tmpdir)
            
            correct_file = code_dir / "hello.py"
            correct_file.write_text("print('hello')")
            
            renamed = provider.post_process_files(code_dir)
            
            assert len(renamed) == 0
            assert correct_file.exists()


class TestAnthropicProvider:
    """Тесты для AnthropicProvider."""
    
    def test_get_model_name_default(self):
        """Тест получения дефолтного названия модели."""
        with patch.dict(os.environ, {}, clear=True):
            provider = AnthropicProvider(api_key="test_key")
            assert provider.get_model_name() == 'claude-3-5-sonnet-20241022'
    
    def test_get_model_name_from_env(self):
        """Тест получения названия модели из конфига."""
        with patch.dict(os.environ, {'ANTHROPIC_MODEL_NAME': 'claude-custom'}):
            provider = AnthropicProvider(api_key="test_key")
            assert provider.get_model_name() == 'claude-custom'
    
    def test_configure_aider_command(self):
        """Тест настройки команды aider."""
        provider = AnthropicProvider(api_key="test_key")
        base_cmd = ['aider', '--yes-always']
        env = {}
        
        cmd, new_env = provider.configure_aider_command(base_cmd, env)
        
        assert '--model' in cmd
        assert 'claude-3-5-sonnet-20241022' in cmd
        assert new_env['ANTHROPIC_API_KEY'] == 'test_key'
    
    def test_post_process_files(self):
        """Тест пост-обработки файлов (должна быть пустой)."""
        provider = AnthropicProvider(api_key="test_key")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = Path(tmpdir)
            renamed = provider.post_process_files(code_dir)
            assert len(renamed) == 0


class TestChatGPTProvider:
    """Тесты для ChatGPTProvider."""
    
    def test_get_model_name_default(self):
        """Тест получения дефолтного названия модели."""
        with patch.dict(os.environ, {}, clear=True):
            provider = ChatGPTProvider(api_key="test_key")
            assert provider.get_model_name() == 'gpt-4'
    
    def test_get_model_name_from_env(self):
        """Тест получения названия модели из конфига."""
        with patch.dict(os.environ, {'CHATGPT_MODEL_NAME': 'gpt-4-turbo'}):
            provider = ChatGPTProvider(api_key="test_key")
            assert provider.get_model_name() == 'gpt-4-turbo'
    
    def test_configure_aider_command(self):
        """Тест настройки команды aider."""
        provider = ChatGPTProvider(api_key="test_key")
        base_cmd = ['aider', '--yes-always']
        env = {}
        
        cmd, new_env = provider.configure_aider_command(base_cmd, env)
        
        assert '--model' in cmd
        assert 'gpt-4' in cmd
        assert new_env['OPENAI_API_KEY'] == 'test_key'
    
    def test_post_process_files(self):
        """Тест пост-обработки файлов (должна быть пустой)."""
        provider = ChatGPTProvider(api_key="test_key")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = Path(tmpdir)
            renamed = provider.post_process_files(code_dir)
            assert len(renamed) == 0


class TestLLMProviderFactory:
    """Тесты для LLMProviderFactory."""
    
    def test_create_provider_deepseek(self):
        """Тест создания провайдера DeepSeek."""
        provider = LLMProviderFactory.create_provider('DEEPSEEK', 'test_key')
        assert isinstance(provider, DeepSeekProvider)
        assert provider.api_key == 'test_key'
    
    def test_create_provider_anthropic(self):
        """Тест создания провайдера Anthropic."""
        provider = LLMProviderFactory.create_provider('ANTHROPIC', 'test_key')
        assert isinstance(provider, AnthropicProvider)
        assert provider.api_key == 'test_key'
    
    def test_create_provider_chatgpt(self):
        """Тест создания провайдера ChatGPT."""
        provider = LLMProviderFactory.create_provider('CHATGPT', 'test_key')
        assert isinstance(provider, ChatGPTProvider)
        assert provider.api_key == 'test_key'
    
    def test_create_provider_invalid(self):
        """Тест создания провайдера с неподдерживаемым типом."""
        with pytest.raises(ValueError, match="Неподдерживаемый тип LLM"):
            LLMProviderFactory.create_provider('INVALID', 'test_key')
    
    def test_get_supported_providers(self):
        """Тест получения списка поддерживаемых провайдеров."""
        providers = LLMProviderFactory.get_supported_providers()
        assert 'DEEPSEEK' in providers
        assert 'ANTHROPIC' in providers
        assert 'CHATGPT' in providers
