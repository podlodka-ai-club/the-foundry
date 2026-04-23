"""
Скрипт для автоматического выполнения задач через AI-агента aider.

Основные возможности:
- Загрузка задач из файлов или создание новых
- Запуск aider с настройками из .env
- Логирование результатов выполнения
- Поддержка различных LLM провайдеров (DeepSeek, Anthropic, ChatGPT)

Архитектура:
- Использует паттерн Factory для создания провайдеров LLM
- Разделение ответственности согласно SOLID принципам
- Каждый провайдер имеет свою пост-обработку
"""

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

from aider.providers import LLMProviderFactory
from aider.core import TaskManager, LogManager, AiderRunner




def main():
    """
    Главная функция скрипта.
    
    Использует новую архитектуру с разделением ответственности:
    - TaskManager для работы с задачами
    - LLMProviderFactory для создания провайдеров
    - AiderRunner для запуска aider
    - LogManager для сохранения логов
    
    Коды возврата:
    - 0: Задача выполнена успешно
    - 1: Ошибка выполнения
    """
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description='AI-агент для автоматического выполнения задач через aider'
    )
    parser.add_argument('--task', required=True, help='Номер задачи (обязательный)')
    parser.add_argument('--prompt', help='Текст задачи (необязательный)')
    
    args = parser.parse_args()
    
    task_id = args.task
    prompt = args.prompt
    
    try:
        task_manager = TaskManager()
        
        if not task_manager.validate_task_id(task_id):
            print("Ошибка: номер задачи некорректный. Проверьте значение параметра --task.")
            sys.exit(1)
        
        provider = LLMProviderFactory.create_from_env()
        
        print(f"Выполнение задачи {task_id}...")
        print(f"Используется провайдер: {provider.get_provider_name()}")
        print(f"Модель: {provider.get_model_name()}")
        
        task_text, task_file = task_manager.load_or_create_task(task_id, prompt)
        
        runner = AiderRunner()
        aider_result = runner.run(task_text, provider)
        
        code_dir = Path(__file__).parent.parent / 'code'
        renamed_files = provider.post_process_files(code_dir)
        
        log_manager = LogManager()
        log_file = log_manager.save_log(
            task_manager.get_log_file_path(task_id),
            task_id,
            task_text,
            aider_result['output'],
            aider_result['success'],
            renamed_files
        )
        
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
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
