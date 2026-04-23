import os
import subprocess
from pathlib import Path
from typing import Dict, List

from aider.providers.base import BaseLLMProvider


class AiderRunner:
    """
    Класс для запуска aider с различными LLM провайдерами.
    
    Отвечает за:
    - Формирование команды aider
    - Запуск aider в нужной директории
    - Обработку результатов выполнения
    """
    
    def __init__(self, code_dir: Path = None):
        """
        Инициализация runner'а.
        
        Args:
            code_dir: Директория с кодом (по умолчанию из AGENT_SOURCES_DIR)
        """
        project_root = Path(__file__).parent.parent.parent
        self.code_dir = code_dir or (project_root / os.getenv('AGENT_SOURCES_DIR', 'code'))
        
        if not self.code_dir.exists():
            self.code_dir.mkdir(parents=True, exist_ok=True)
    
    def run(
        self,
        task_text: str,
        provider: BaseLLMProvider,
        timeout: int = 600
    ) -> Dict[str, any]:
        """
        Запуск aider для выполнения задачи.
        
        Args:
            task_text: Текст задачи для выполнения
            provider: Провайдер LLM
            timeout: Таймаут выполнения в секундах (по умолчанию 10 минут)
            
        Returns:
            Словарь с результатами: {'success': bool, 'output': str, 'returncode': int}
        """
        env = os.environ.copy()
        
        base_cmd = ['aider', '--yes-always', '--no-git']
        
        aider_cmd, env = provider.configure_aider_command(base_cmd, env)
        
        existing_files = self._get_existing_files()
        if existing_files:
            aider_cmd.extend(existing_files)
        
        aider_cmd.extend(['--message', task_text])
        
        try:
            result = subprocess.run(
                aider_cmd,
                cwd=self.code_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout + result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': f'Ошибка: превышено время ожидания выполнения задачи ({timeout} секунд)',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'output': f'Ошибка при запуске aider: {str(e)}',
                'returncode': -1
            }
    
    def _get_existing_files(self) -> List[str]:
        """
        Получение списка существующих файлов для контекста aider.
        
        Returns:
            Список имен файлов .py в директории code
        """
        existing_files = list(self.code_dir.glob('*.py'))
        return [str(file.name) for file in existing_files]
