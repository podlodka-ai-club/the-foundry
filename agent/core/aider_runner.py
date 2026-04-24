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
        
        Raises:
            ValueError: Если code_dir небезопасен или находится в защищенной зоне
        """
        project_root = Path(__file__).parent.parent.parent
        
        if code_dir is None:
            sources_dir = os.getenv('AGENT_SOURCES_DIR', 'code')
            sources_path = Path(sources_dir)
            
            # Если абсолютный путь
            if sources_path.is_absolute():
                code_dir = self._validate_absolute_path(sources_path)
            else:
                # Относительный путь - проверяем на '..'
                if '..' in sources_path.parts:
                    raise ValueError(
                        f"AGENT_SOURCES_DIR не должен содержать '..': {sources_dir}\n"
                        f"Используйте относительный путь без '..' или абсолютный путь с AGENT_ALLOW_ABSOLUTE_PATHS=true"
                    )
                
                code_dir = project_root / sources_dir
        
        self.code_dir = code_dir
        
        if not self.code_dir.exists():
            try:
                self.code_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                raise ValueError(
                    f"Нет прав на создание директории: {self.code_dir}"
                )
    
    def _validate_absolute_path(self, sources_path: Path) -> Path:
        """
        Валидация абсолютного пути.
        
        Args:
            sources_path: Абсолютный путь для проверки
        
        Returns:
            Валидированный путь
        
        Raises:
            ValueError: Если путь находится в защищенной зоне или не подтвержден
        """
        # Whitelist опасных директорий
        dangerous_paths = [
            Path('/etc'),
            Path('/usr'),
            Path('/bin'),
            Path('/sbin'),
            Path('/boot'),
            Path('/sys'),
            Path('/proc'),
            Path('/dev'),
            Path('/var'),
            Path('/root'),
        ]
        
        # Добавляем конфиденциальные директории пользователя
        try:
            home = Path.home()
            dangerous_paths.extend([
                home / '.ssh',
                home / '.config',
                home / '.gnupg',
            ])
        except Exception:
            pass  # Если не можем определить home, пропускаем
        
        # Проверяем, не находится ли путь в опасной зоне
        resolved_path = sources_path.resolve()
        for dangerous in dangerous_paths:
            try:
                dangerous_resolved = dangerous.resolve()
                resolved_path.relative_to(dangerous_resolved)
                raise ValueError(
                    f"Запрещено использовать директорию: {resolved_path}\n"
                    f"Она находится в защищенной зоне: {dangerous_resolved}\n"
                    f"Используйте безопасную директорию (например, /tmp или ~/projects)"
                )
            except ValueError as e:
                # relative_to выбрасывает ValueError если пути не связаны
                if "does not start with" not in str(e) and "is not in the subpath" not in str(e):
                    raise
        
        # Требуем явного подтверждения через env переменную
        if not os.getenv('AGENT_ALLOW_ABSOLUTE_PATHS', '').lower() == 'true':
            raise ValueError(
                f"Использование абсолютного пути требует явного подтверждения.\n"
                f"Путь: {sources_path}\n"
                f"Добавьте в .env: AGENT_ALLOW_ABSOLUTE_PATHS=true"
            )
        
        return sources_path
    
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
        debug_info = ""
        # debug_info += "=== DEBUG: Команда aider ===\n"
        # debug_info += f"CWD: {self.code_dir}\n"
        # debug_info += f"CMD: {' '.join(aider_cmd)}\n"
        # debug_info += f"Files: {existing_files}\n"
        # debug_info += "=" * 50 + "\n\n"
        
        # Выводим в консоль для отладки
        # print(debug_info)
        
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
