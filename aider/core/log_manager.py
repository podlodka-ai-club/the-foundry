from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


class LogManager:
    """
    Менеджер для работы с логами выполнения задач.
    
    Отвечает за:
    - Сохранение логов выполнения
    - Форматирование логов в markdown
    - Добавление информации о пост-обработке
    """
    
    def save_log(
        self,
        log_file: Path,
        task_id: str,
        task_text: str,
        aider_output: str,
        success: bool,
        renamed_files: List[Tuple[str, str]] = None
    ) -> Path:
        """
        Сохранение лога выполнения задачи.
        
        Args:
            log_file: Путь к лог-файлу
            task_id: Номер задачи
            task_text: Текст задачи
            aider_output: Вывод aider
            success: Успешность выполнения
            renamed_files: Список переименованных файлов (опционально)
            
        Returns:
            Path объект с путем к созданному лог-файлу
        """
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = "Успешно выполнено" if success else "Ошибка выполнения"
        
        commit_msg = ""
        if success:
            commit_msg = f"Задача {task_id} выполнена автоматически через aider"
        
        output = aider_output
        
        if renamed_files:
            rename_info = "\n\n--- Пост-обработка ---\nПереименованные файлы:\n"
            for old_name, new_name in renamed_files:
                rename_info += f"  {old_name} -> {new_name}\n"
            output += rename_info
        
        log_content = f"""# Лог выполнения задачи {task_id}

**Дата:** {timestamp}

## Исходный промт

{task_text}

## Вывод aider

```
{output}
```

## Комментарий для коммита

{commit_msg}

## Статус

{status}
"""
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(log_content)
        
        return log_file
    
    def format_post_process_info(self, renamed_files: List[Tuple[str, str]]) -> str:
        """
        Форматирование информации о пост-обработке.
        
        Args:
            renamed_files: Список кортежей (старое_имя, новое_имя)
            
        Returns:
            Отформатированная строка с информацией о переименованиях
        """
        if not renamed_files:
            return ""
        
        info = "\n\n--- Пост-обработка ---\nПереименованные файлы:\n"
        for old_name, new_name in renamed_files:
            info += f"  {old_name} -> {new_name}\n"
        
        return info
