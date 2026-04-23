import os
import subprocess
import pytest
from pathlib import Path
from datetime import datetime


class TestLLMIntegration:
    """
    Интеграционные тесты для проверки работы LLM агента.
    
    Эти тесты выполняют реальные вызовы к LLM и проверяют,
    что агент корректно создает и редактирует файлы.
    
    ВАЖНО: Для запуска этих тестов требуется:
    - Настроенный .env с API ключами
    - Доступ к LLM API (DeepSeek/Anthropic/ChatGPT)
    - Docker для запуска агента
    """
    
    @pytest.fixture
    def project_root(self):
        """Получение корневой директории проекта."""
        return Path(__file__).parent.parent
    
    @pytest.fixture
    def code_dir(self, project_root):
        """Получение директории с кодом."""
        return project_root / 'code'
    
    @pytest.fixture
    def cleanup_current_dt(self, code_dir):
        """Фикстура для удаления current_dt.py перед тестом."""
        current_dt_file = code_dir / 'current_dt.py'
        if current_dt_file.exists():
            current_dt_file.unlink()
        yield
        # Cleanup после теста не нужен - файл должен остаться
    
    @pytest.fixture
    def setup_hello_py(self, code_dir):
        """Фикстура для создания hello.py с базовым содержимым."""
        hello_file = code_dir / 'hello.py'
        hello_file.write_text('print(f"Hello!")\n', encoding='utf-8')
        yield
        # Cleanup после теста не нужен - файл должен остаться
    
    @pytest.mark.integration
    def test_create_current_dt_script(self, project_root, code_dir, cleanup_current_dt):
        """
        Тест №1: Создание скрипта current_dt.py через LLM агента.
        
        Проверяет:
        1. Файл current_dt.py удален перед тестом
        2. Команда make runagent task=TF-1 выполняется успешно
        3. Файл current_dt.py создан
        4. Скрипт запускается и выводит текущую дату/время
        """
        current_dt_file = code_dir / 'current_dt.py'
        
        # Проверяем, что файл удален
        assert not current_dt_file.exists(), "Файл current_dt.py должен быть удален перед тестом"
        
        # Выполняем команду через make
        result = subprocess.run(
            ['make', 'runagent', 'task=TF-1'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120  # 2 минуты на выполнение
        )
        
        # Проверяем успешность выполнения
        assert result.returncode == 0, f"Команда завершилась с ошибкой:\n{result.stderr}\n{result.stdout}"
        
        # Проверяем, что файл создан
        assert current_dt_file.exists(), "Файл current_dt.py не был создан"
        
        # Запускаем скрипт и проверяем вывод
        script_result = subprocess.run(
            ['python', str(current_dt_file)],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert script_result.returncode == 0, f"Скрипт завершился с ошибкой:\n{script_result.stderr}"
        
        output = script_result.stdout.strip()
        
        # Проверяем формат вывода (должна быть дата/время)
        # Пример: 2026-04-23 22:26:45
        assert len(output) > 0, "Скрипт не вывел дату/время"
        
        # Проверяем, что вывод содержит текущую дату
        current_date = datetime.now().strftime('%Y-%m-%d')
        assert current_date in output, f"Вывод не содержит текущую дату. Получено: {output}"
        
        # Проверяем формат времени (должно быть HH:MM:SS)
        parts = output.split()
        assert len(parts) >= 2, f"Неверный формат вывода: {output}"
        
        time_part = parts[1]
        time_components = time_part.split(':')
        assert len(time_components) == 3, f"Неверный формат времени: {time_part}"
        
        # Проверяем, что компоненты времени - числа
        for component in time_components:
            assert component.isdigit(), f"Неверный компонент времени: {component}"
    
    @pytest.mark.integration
    def test_modify_hello_script(self, project_root, code_dir, setup_hello_py):
        """
        Тест №2: Модификация скрипта hello.py через LLM агента.
        
        Проверяет:
        1. Файл hello.py создан с базовым содержимым
        2. Команда make runagent task=TF-2 выполняется успешно
        3. Скрипт запускается, запрашивает имя и выводит приветствие
        """
        hello_file = code_dir / 'hello.py'
        
        # Проверяем, что файл создан с базовым содержимым
        assert hello_file.exists(), "Файл hello.py должен быть создан"
        content = hello_file.read_text(encoding='utf-8')
        assert 'print(f"Hello!")' in content, "Файл должен содержать базовое приветствие"
        
        # Выполняем команду через make
        result = subprocess.run(
            ['make', 'runagent', 'task=TF-2'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120  # 2 минуты на выполнение
        )
        
        # Проверяем успешность выполнения
        assert result.returncode == 0, f"Команда завершилась с ошибкой:\n{result.stderr}\n{result.stdout}"
        
        # Запускаем скрипт с вводом имени
        script_result = subprocess.run(
            ['python', str(hello_file)],
            input='Test\n',  # Вводим имя "Test"
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert script_result.returncode == 0, f"Скрипт завершился с ошибкой:\n{script_result.stderr}"
        
        output = script_result.stdout.strip()
        
        # Проверяем, что скрипт запрашивает имя
        assert 'name' in output.lower() or 'имя' in output.lower(), \
            f"Скрипт не запрашивает имя. Вывод: {output}"
        
        # Проверяем, что вывод содержит приветствие с именем
        # Возможные варианты: "Hello, Test!", "Привет, Test!", etc.
        assert 'Test' in output, f"Вывод не содержит введенное имя. Получено: {output}"
        
        # Проверяем наличие приветствия
        output_lower = output.lower()
        greeting_found = any(word in output_lower for word in ['hello', 'привет', 'hi'])
        assert greeting_found, f"Вывод не содержит приветствие. Получено: {output}"
