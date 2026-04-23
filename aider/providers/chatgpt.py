from pathlib import Path
from typing import Dict, List, Tuple

from .base import BaseLLMProvider


class ChatGPTProvider(BaseLLMProvider):
    """
    Провайдер для работы с OpenAI ChatGPT LLM.
    
    Особенности:
    - Использует переменную окружения OPENAI_API_KEY
    - Не требует пост-обработки файлов (пока)
    """
    
    def get_model_name(self) -> str:
        """Получение названия модели GPT."""
        return 'gpt-4'
    
    def configure_aider_command(self, base_cmd: List[str], env: Dict[str, str]) -> Tuple[List[str], Dict[str, str]]:
        """
        Настройка команды aider для ChatGPT.
        
        Args:
            base_cmd: Базовая команда aider
            env: Переменные окружения
            
        Returns:
            Кортеж (команда с параметрами ChatGPT, переменные окружения с API ключом)
        """
        cmd = base_cmd.copy()
        cmd.extend(['--model', self.get_model_name()])
        
        env_copy = env.copy()
        env_copy['OPENAI_API_KEY'] = self.api_key
        
        return cmd, env_copy
    
    def post_process_files(self, code_dir: Path) -> List[Tuple[str, str]]:
        """
        Пост-обработка файлов для ChatGPT.
        
        GPT обычно создает файлы с правильными именами,
        поэтому пост-обработка не требуется.
        
        Args:
            code_dir: Директория с кодом
            
        Returns:
            Пустой список (нет переименованных файлов)
        """
        return []
