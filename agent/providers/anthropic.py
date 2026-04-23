import os
from pathlib import Path
from typing import Dict, List, Tuple

from .base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """
    Провайдер для работы с Anthropic Claude LLM.
    
    Особенности:
    - Использует переменную окружения ANTHROPIC_API_KEY
    - Не требует пост-обработки файлов (пока)
    - Имя модели читается из ANTHROPIC_MODEL_NAME или используется дефолтное
    """
    
    DEFAULT_MODEL = 'claude-3-5-sonnet-20241022'
    
    def get_model_name(self) -> str:
        """Получение названия модели Claude из конфига или дефолтное."""
        return os.getenv('ANTHROPIC_MODEL_NAME', self.DEFAULT_MODEL)
    
    def configure_aider_command(self, base_cmd: List[str], env: Dict[str, str]) -> Tuple[List[str], Dict[str, str]]:
        """
        Настройка команды aider для Anthropic.
        
        Args:
            base_cmd: Базовая команда aider
            env: Переменные окружения
            
        Returns:
            Кортеж (команда с параметрами Anthropic, переменные окружения с API ключом)
        """
        cmd = base_cmd.copy()
        cmd.extend(['--model', self.get_model_name()])
        
        env_copy = env.copy()
        env_copy['ANTHROPIC_API_KEY'] = self.api_key
        
        return cmd, env_copy
    
    def post_process_files(self, code_dir: Path) -> List[Tuple[str, str]]:
        """
        Пост-обработка файлов для Anthropic.
        
        Claude обычно создает файлы с правильными именами,
        поэтому пост-обработка не требуется.
        
        Args:
            code_dir: Директория с кодом
            
        Returns:
            Пустой список (нет переименованных файлов)
        """
        return []
