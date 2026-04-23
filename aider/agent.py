"""
Скрипт для автоматического выполнения задач через AI-агента aider.

Основные возможности:
- Загрузка задач из файлов или создание новых
- Запуск aider с настройками из .env
- Логирование результатов выполнения
- Поддержка различных LLM провайдеров (DeepSeek, Anthropic, ChatGPT)
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv


def validate_task_id(task_id: str) -> bool:
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


def load_env_settings() -> dict:
    """
    Загрузка настроек LLM из файла .env.
    
    Читает переменные окружения и формирует настройки для выбранной LLM:
    - CODING_LLM - выбор провайдера (DEEPSEEK, ANTHROPIC, CHATGPT)
    - Соответствующий API ключ
    - Название модели
    
    Returns:
        Словарь с настройками: {'llm': str, 'api_key': str, 'model': str}
        
    Raises:
        ValueError: Если API ключ не найден в .env файле
    """
    load_dotenv()
    
    coding_llm = os.getenv('CODING_LLM', 'DEEPSEEK')
    
    settings = {
        'llm': coding_llm,
        'api_key': None,
        'model': None
    }
    
    if coding_llm == 'DEEPSEEK':
        settings['api_key'] = os.getenv('DEEPSEEK_API_KEY')
        settings['model'] = 'deepseek/deepseek-chat'
    elif coding_llm == 'ANTHROPIC':
        settings['api_key'] = os.getenv('ANTHROPIC_API_KEY')
        settings['model'] = 'claude-3-5-sonnet-20241022'
    elif coding_llm == 'CHATGPT':
        settings['api_key'] = os.getenv('CHATGPT_API_KEY')
        settings['model'] = 'gpt-4'
    
    if not settings['api_key']:
        raise ValueError(f"API ключ для {coding_llm} не найден в .env файле")
    
    return settings


def get_task_file_path(task_id: str) -> Path:
    """
    Получение пути к файлу задачи.
    
    Формирует путь: <project_root>/<TASKS_DIR>/<task_id>/<task_id>_task.md
    
    Args:
        task_id: Номер задачи
        
    Returns:
        Path объект с путем к файлу задачи
    """
    tasks_dir = os.getenv('TASKS_DIR', 'aider/tasks')
    project_root = Path(__file__).parent.parent
    return project_root / tasks_dir / task_id / f"{task_id}_task.md"


def get_log_file_path(task_id: str) -> Path:
    """
    Получение пути к лог-файлу задачи.
    
    Формирует путь: <project_root>/<TASKS_DIR>/<task_id>/<task_id>_log.md
    
    Args:
        task_id: Номер задачи
        
    Returns:
        Path объект с путем к лог-файлу
    """
    tasks_dir = os.getenv('TASKS_DIR', 'aider/tasks')
    project_root = Path(__file__).parent.parent
    return project_root / tasks_dir / task_id / f"{task_id}_log.md"


def load_or_create_task(task_id: str, prompt: str | None) -> tuple[str, Path]:
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
    task_file = get_task_file_path(task_id)
    
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


def run_aider(task_text: str, task_id: str, llm_settings: dict) -> dict:
    """
    Запуск aider для выполнения задачи.
    
    Формирует команду запуска aider с учетом выбранной LLM:
    - DeepSeek: использует --api-key deepseek=<key>
    - Anthropic/ChatGPT: использует переменные окружения
    
    Все изменения выполняются только в папке code/.
    
    Args:
        task_text: Текст задачи для выполнения
        task_id: Номер задачи
        llm_settings: Настройки LLM из load_env_settings()
        
    Returns:
        Словарь с результатами: {'success': bool, 'output': str, 'returncode': int}
    """
    project_root = Path(__file__).parent.parent
    code_dir = project_root / os.getenv('SOURCES_DIR', 'code')
    
    if not code_dir.exists():
        code_dir.mkdir(parents=True, exist_ok=True)
    
    env = os.environ.copy()
    
    aider_cmd = ['aider', '--yes-always', '--no-auto-commits']
    
    if llm_settings['llm'] == 'DEEPSEEK':
        aider_cmd.extend([
            '--model', llm_settings['model'],
            '--api-key', f"deepseek={llm_settings['api_key']}"
        ])
    elif llm_settings['llm'] == 'ANTHROPIC':
        env['ANTHROPIC_API_KEY'] = llm_settings['api_key']
        aider_cmd.extend(['--model', llm_settings['model']])
    elif llm_settings['llm'] == 'CHATGPT':
        env['OPENAI_API_KEY'] = llm_settings['api_key']
        aider_cmd.extend(['--model', llm_settings['model']])
    
    aider_cmd.extend(['--message', task_text])
    
    try:
        result = subprocess.run(
            aider_cmd,
            cwd=code_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        return {
            'success': result.returncode == 0,
            'output': result.stdout + result.stderr,
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': 'Ошибка: превышено время ожидания выполнения задачи (10 минут)',
            'returncode': -1
        }
    except Exception as e:
        return {
            'success': False,
            'output': f'Ошибка при запуске aider: {str(e)}',
            'returncode': -1
        }


def save_log(task_id: str, task_text: str, aider_result: dict):
    """
    Сохранение лога выполнения задачи в markdown файл.
    
    Создает структурированный лог с разделами:
    - Дата выполнения
    - Исходный промт
    - Вывод aider
    - Комментарий для коммита
    - Статус выполнения
    
    Args:
        task_id: Номер задачи
        task_text: Текст задачи
        aider_result: Результат выполнения из run_aider()
        
    Returns:
        Path объект с путем к созданному лог-файлу
    """
    log_file = get_log_file_path(task_id)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    status = "Успешно выполнено" if aider_result['success'] else "Ошибка выполнения"
    
    commit_msg = ""
    if aider_result['success']:
        commit_msg = f"Задача {task_id} выполнена автоматически через aider"
    
    log_content = f"""# Лог выполнения задачи {task_id}

**Дата:** {timestamp}

## Исходный промт

{task_text}

## Вывод aider

```
{aider_result['output']}
```

## Комментарий для коммита

{commit_msg}

## Статус

{status}
"""
    
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(log_content)
    
    return log_file


def main():
    """
    Главная функция скрипта.
    
    Выполняет следующие шаги:
    1. Парсинг аргументов командной строки
    2. Валидация номера задачи
    3. Загрузка настроек LLM
    4. Загрузка или создание задачи
    5. Запуск aider
    6. Сохранение лога
    7. Вывод результата
    
    Коды возврата:
    - 0: Задача выполнена успешно
    - 1: Ошибка выполнения
    """
    parser = argparse.ArgumentParser(
        description='AI-агент для автоматического выполнения задач через aider'
    )
    parser.add_argument('--task', required=True, help='Номер задачи (обязательный)')
    parser.add_argument('--prompt', help='Текст задачи (необязательный)')
    
    args = parser.parse_args()
    
    if not args.task or not validate_task_id(args.task):
        print("Ошибка: номер задачи не указан или некорректный. Проверьте значение параметра --task.")
        sys.exit(1)
    
    task_id = args.task
    prompt = args.prompt
    
    try:
        llm_settings = load_env_settings()
        
        print(f"Выполнение задачи {task_id}...")
        
        task_text, task_file = load_or_create_task(task_id, prompt)
        
        aider_result = run_aider(task_text, task_id, llm_settings)
        
        log_file = save_log(task_id, task_text, aider_result)
        
        if aider_result['success']:
            print(f"Задача выполнена, лог работ сохранен в файл: {log_file}")
            sys.exit(0)
        else:
            print(f"Ошибка выполнения задачи. Лог работ сохранен в файл: {log_file}")
            sys.exit(1)
            
    except FileNotFoundError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
