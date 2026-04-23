import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

from .base import BaseLLMProvider


class DeepSeekProvider(BaseLLMProvider):
    """
    Провайдер для работы с DeepSeek LLM.
    
    Особенности:
    - Использует формат --api-key deepseek=<key>
    - Требует пост-обработку файлов (DeepSeek выводит рассуждения в именах файлов)
    - Имя модели читается из DEEPSEEK_MODEL_NAME или используется дефолтное
    """
    
    DEFAULT_MODEL = 'deepseek/deepseek-chat'
    
    def get_model_name(self) -> str:
        """Получение названия модели DeepSeek из конфига или дефолтное."""
        return os.getenv('DEEPSEEK_MODEL_NAME', self.DEFAULT_MODEL)
    
    def configure_aider_command(self, base_cmd: List[str], env: Dict[str, str]) -> Tuple[List[str], Dict[str, str]]:
        """
        Настройка команды aider для DeepSeek.
        
        Args:
            base_cmd: Базовая команда aider
            env: Переменные окружения
            
        Returns:
            Кортеж (команда с параметрами DeepSeek, переменные окружения с API ключом)
        """
        cmd = base_cmd.copy()
        cmd.extend(['--model', self.get_model_name()])
        
        env_copy = env.copy()
        env_copy['DEEPSEEK_API_KEY'] = self.api_key
        
        return cmd, env_copy
    
    def post_process_files(self, code_dir: Path) -> List[Tuple[str, str]]:
        """
        Пост-обработка файлов для DeepSeek.
        
        DeepSeek иногда выводит промежуточные рассуждения перед именем файла:
        - "Let's produce the SEARCH/REPLACE block.current_dt.py"
        - "Let's do it.factorial.py"
        - "Let's craft the block.sum_two_numbers.py"
        
        Функция находит такие файлы и переименовывает их.
        
        Args:
            code_dir: Директория с кодом
            
        Returns:
            Список кортежей (старое_имя, новое_имя) переименованных файлов
        """
        renamed_files = []
        
        def extract_correct_name(name: str) -> str:
            """
            Извлекает правильное имя файла из неправильного.
            
            Использует regex для поиска валидного имени файла в конце строки.
            Валидное имя: буквы, цифры, подчеркивания, дефисы + расширение.
            """
            match = re.search(r'([a-zA-Z0-9_-]+\.[a-zA-Z0-9]+)$', name)
            if match:
                return match.group(1)
            
            parts = name.split('.')
            if len(parts) >= 2:
                return '.'.join(parts[-2:])
            
            return name
        
        def is_malformed(name: str) -> bool:
            """Проверяет, является ли имя файла неправильным."""
            bad_patterns = [
                "Let's ",
                "SEARCH/REPLACE",
                "REPLACE block",
                "produce the",
                "craft the"
            ]
            
            for pattern in bad_patterns:
                if pattern in name:
                    return True
            
            if ' ' in name and not name.startswith('.'):
                return True
            
            return False
        
        for item in code_dir.iterdir():
            item_name = item.name
            
            if item_name.startswith('.'):
                continue
            
            if is_malformed(item_name):
                try:
                    if item.is_dir():
                        for file in item.iterdir():
                            correct_file_name = extract_correct_name(file.name)
                            new_file_path = code_dir / correct_file_name
                            file.rename(new_file_path)
                            renamed_files.append((f"{item_name}/{file.name}", correct_file_name))
                        item.rmdir()
                    else:
                        correct_name = extract_correct_name(item_name)
                        new_path = code_dir / correct_name
                        
                        if correct_name != item_name:
                            item.rename(new_path)
                            renamed_files.append((item_name, correct_name))
                except Exception as e:
                    print(f"Ошибка при переименовании {item_name}: {e}")
        
        return renamed_files
