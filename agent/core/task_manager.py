import os
import re
from pathlib import Path
from typing import Tuple


class TaskManager:
    """
    Менеджер для работы с задачами.
    
    Отвечает за:
    - Валидацию номеров задач
    - Загрузку задач из файлов
    - Создание новых задач
    - Получение путей к файлам задач
    """
    
    def __init__(self, tasks_dir: str = None):
        """
        Инициализация менеджера задач.
        
        Args:
            tasks_dir: Директория с задачами (по умолчанию из AGENT_TASKS_DIR)
        """
        self.tasks_dir = tasks_dir or os.getenv('AGENT_TASKS_DIR', 'agent/tasks')
        self.project_root = Path(__file__).parent.parent.parent
    
    def validate_task_id(self, task_id: str) -> bool:
        """
        Валидация номера задачи.
        
        Номер задачи может содержать:
        - Латинские буквы (A-Z, a-z)
        - Цифры (0-9)
        - Дефис (-)
        
        Args:
            task_id: Номер задачи для проверки
            
        Returns:
            True если номер валиден, False в противном случае
        """
        pattern = r'^[A-Za-z0-9\-]+$'
        return bool(re.match(pattern, task_id)) and len(task_id) > 0
    
    def get_task_file_path(self, task_id: str) -> Path:
        """
        Получение пути к файлу задачи.
        
        Args:
            task_id: Номер задачи
            
        Returns:
            Path объект с путем к файлу задачи
        """
        return self.project_root / self.tasks_dir / task_id / f"{task_id}_task.md"
    
    def get_log_file_path(self, task_id: str) -> Path:
        """
        Получение пути к лог-файлу задачи.
        
        Args:
            task_id: Номер задачи
            
        Returns:
            Path объект с путем к лог-файлу
        """
        return self.project_root / self.tasks_dir / task_id / f"{task_id}_log.md"
    
    def load_or_create_task(self, task_id: str, prompt: str = None) -> Tuple[str, Path]:
        """
        Загрузка существующей задачи или создание новой.
        
        Логика работы:
        1. Если указан prompt и файл существует - склеивает содержимое
        2. Если указан prompt и файл не существует - создает новый файл
        3. Если prompt не указан - читает существующий файл
        
        Args:
            task_id: Номер задачи
            prompt: Текст задачи (опционально)
            
        Returns:
            Кортеж (текст_задачи, путь_к_файлу)
            
        Raises:
            FileNotFoundError: Если файл не найден и prompt не указан
        """
        task_file = self.get_task_file_path(task_id)
        
        if prompt:
            if task_file.exists():
                with open(task_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                task_text = f"{existing_content}\n\n{prompt}"
            else:
                task_file.parent.mkdir(parents=True, exist_ok=True)
                task_text = prompt
                with open(task_file, 'w', encoding='utf-8') as f:
                    f.write(task_text)
        else:
            if not task_file.exists():
                raise FileNotFoundError(
                    f"Файл задачи не найден: {task_file}\n"
                    f"Создайте файл задачи или укажите параметр --prompt"
                )
            with open(task_file, 'r', encoding='utf-8') as f:
                task_text = f.read()
        
        return task_text, task_file
