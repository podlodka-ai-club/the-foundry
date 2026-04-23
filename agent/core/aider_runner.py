import os
import subprocess
from pathlib import Path
from typing import Dict, List

from agent.providers.base import BaseLLMProvider

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
        
        # Базовая команда с флагами:
        # --yes-always: автоматически подтверждать все действия
        # --no-git: отключить git (мы управляем git вручную)
        base_cmd = ['aider', '--yes-always', '--no-git']
        
        # Провайдер добавляет свои параметры (--model, API ключи через env)
        aider_cmd, env = provider.configure_aider_command(base_cmd, env)
        
        # Добавляем все существующие файлы для редактирования
        # Используем --file для явного указания файлов, которые aider может редактировать
        existing_files = self._get_existing_files()
        for file in existing_files:
            aider_cmd.extend(['--file', file])
        
        aider_cmd.extend(['--message', task_text])
        
        # Отладочная информация: логируем команду
        debug_info = "=== DEBUG: Команда aider ===\n"
        debug_info += f"CWD: {self.code_dir}\n"
        debug_info += f"CMD: {' '.join(aider_cmd)}\n"
        debug_info += f"Files: {existing_files}\n"
        debug_info += "=" * 50 + "\n\n"
        
        # Выводим в консоль для отладки
        print(debug_info)
        
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
                'output': debug_info + result.stdout + result.stderr,
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
        
        Возвращает все файлы в директории code (любые расширения),
        исключая служебные файлы aider (.aider.*).
        
        Returns:
            Список имен файлов в директории code
        """
        all_files = [f for f in self.code_dir.iterdir() if f.is_file()]
        # Исключаем служебные файлы aider
        existing_files = [f for f in all_files if not f.name.startswith('.aider')]
        return [str(file.name) for file in existing_files]
