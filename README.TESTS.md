- [О проекте](README.md)
- [Кодинг агент](README.AGENT.md)
- [Тесты](#)

# Документация по тестам

Проект использует **pytest** для тестирования всех компонентов системы.

---

## Структура тестов

```
tests/
├── __init__.py              # Инициализация пакета тестов
├── conftest.py              # Конфигурация pytest (добавление project root в sys.path)
├── test_providers.py        # Тесты провайдеров LLM
└── test_core.py             # Тесты core модулей
```

---

## Запуск тестов

**Все тесты:**
```bash
make test
# или
pytest tests/ -v
```

**Конкретный файл тестов:**
```bash
make test filter=test_providers.py
# или
pytest tests/test_providers.py -v
```

**Конкретный класс тестов:**
```bash
pytest tests/test_providers.py::TestDeepSeekProvider -v
```

**Конкретный тест:**
```bash
pytest tests/test_providers.py::TestDeepSeekProvider::test_get_model_name_default -v
```

**С покрытием кода:**
```bash
pytest tests/ --cov=aider --cov-report=html
```

---

## test_providers.py

Тесты для провайдеров LLM и фабрики.

### TestDeepSeekProvider (6 тестов)

**test_get_model_name_default**
- Проверка получения дефолтного названия модели
- Ожидается: `'deepseek/deepseek-chat'`

**test_get_model_name_from_env**
- Проверка чтения названия модели из переменной окружения `DEEPSEEK_MODEL_NAME`
- Использует `unittest.mock.patch` для изоляции теста

**test_configure_aider_command**
- Проверка настройки команды aider для DeepSeek
- Проверяет передачу API ключа через `env['DEEPSEEK_API_KEY']`
- Проверяет добавление параметра `--model`

**test_post_process_files_malformed_filename**
- Проверка пост-обработки файлов с неправильными именами
- Тестовый файл: `"Let's do it.test.py"` → `"test.py"`
- Проверяет переименование и удаление старого файла

**test_post_process_files_directory**
- Проверка пост-обработки директорий с неправильными именами
- Тестовая директория: `"Let's produce the SEARCH"`
- Файл внутри: `"REPLACE block.script.py"` → `"script.py"`
- Проверяет перемещение файлов и удаление директории

**test_post_process_files_correct_filename**
- Проверка, что файлы с правильными именами не переименовываются
- Тестовый файл: `"hello.py"` остается `"hello.py"`

---

### TestAnthropicProvider (4 теста)

**test_get_model_name_default**
- Проверка дефолтного названия модели
- Ожидается: `'claude-3-5-sonnet-20241022'`

**test_get_model_name_from_env**
- Проверка чтения из `ANTHROPIC_MODEL_NAME`

**test_configure_aider_command**
- Проверка настройки команды aider для Anthropic
- Проверяет передачу API ключа через `env['ANTHROPIC_API_KEY']`

**test_post_process_files**
- Проверка, что пост-обработка возвращает пустой список
- Anthropic не требует пост-обработки файлов

---

### TestChatGPTProvider (4 теста)

**test_get_model_name_default**
- Проверка дефолтного названия модели
- Ожидается: `'gpt-4'`

**test_get_model_name_from_env**
- Проверка чтения из `CHATGPT_MODEL_NAME`

**test_configure_aider_command**
- Проверка настройки команды aider для ChatGPT
- Проверяет передачу API ключа через `env['OPENAI_API_KEY']`

**test_post_process_files**
- Проверка, что пост-обработка возвращает пустой список
- ChatGPT не требует пост-обработки файлов

---

### TestLLMProviderFactory (5 тестов)

**test_create_provider_deepseek**
- Проверка создания провайдера DeepSeek через фабрику
- Проверяет тип и API ключ

**test_create_provider_anthropic**
- Проверка создания провайдера Anthropic через фабрику

**test_create_provider_chatgpt**
- Проверка создания провайдера ChatGPT через фабрику

**test_create_provider_invalid**
- Проверка выброса исключения `ValueError` для неподдерживаемого типа LLM
- Тестовый тип: `'INVALID'`

**test_get_supported_providers**
- Проверка получения списка поддерживаемых провайдеров
- Ожидается: `['DEEPSEEK', 'ANTHROPIC', 'CHATGPT']`

---

## test_core.py

Тесты для core модулей системы.

### TestTaskManager (8 тестов)

**test_validate_task_id_valid**
- Проверка валидации корректных номеров задач
- Валидные: `'TF-1'`, `'AI-123'`, `'TEST'`

**test_validate_task_id_invalid**
- Проверка валидации некорректных номеров задач
- Невалидные: `''`, `'TF 1'`, `'TF@1'`

**test_get_task_file_path**
- Проверка получения пути к файлу задачи
- Формат: `<tasks_dir>/<task_id>/<task_id>_task.md`

**test_get_log_file_path**
- Проверка получения пути к лог-файлу
- Формат: `<tasks_dir>/<task_id>/<task_id>_log.md`

**test_load_or_create_task_new_with_prompt**
- Проверка создания новой задачи с промптом
- Файл создается, содержимое = промпт

**test_load_or_create_task_existing_with_prompt**
- Проверка добавления промпта к существующей задаче
- Содержимое склеивается: `existing + "\n\n" + new`

**test_load_or_create_task_existing_without_prompt**
- Проверка загрузки существующей задачи без промпта
- Возвращается содержимое файла

**test_load_or_create_task_not_found**
- Проверка выброса `FileNotFoundError` для несуществующей задачи без промпта

---

### TestLogManager (5 тестов)

**test_save_log_success**
- Проверка сохранения лога успешного выполнения
- Проверяет наличие: task_id, task_text, output, "Успешно выполнено"

**test_save_log_failure**
- Проверка сохранения лога неуспешного выполнения
- Проверяет наличие: "Ошибка выполнения"

**test_save_log_with_renamed_files**
- Проверка сохранения лога с информацией о переименованных файлах
- Проверяет наличие секции "Пост-обработка"

**test_format_post_process_info**
- Проверка форматирования информации о пост-обработке
- Формат: `"old_name -> new_name"`

**test_format_post_process_info_empty**
- Проверка, что для пустого списка возвращается пустая строка

---

## Конфигурация pytest

**pytest.ini:**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

**conftest.py:**
```python
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
```

Добавляет корень проекта в `sys.path` для корректного импорта модулей.

---

## Используемые инструменты

**pytest** - фреймворк для тестирования
```bash
pip install pytest
```

**unittest.mock** - для изоляции тестов (встроен в Python)
- `patch.dict(os.environ, ...)` - мокирование переменных окружения

**tempfile** - для создания временных файлов и директорий (встроен в Python)
- `tempfile.TemporaryDirectory()` - временная директория, автоматически удаляется

---

## Покрытие кода

Для проверки покрытия кода тестами:

```bash
# Установка pytest-cov
pip install pytest-cov

# Запуск с покрытием
pytest tests/ --cov=aider --cov-report=html

# Просмотр отчета
open htmlcov/index.html
```

---

## Добавление новых тестов

**1. Создать тестовый класс:**
```python
class TestNewFeature:
    """Тесты для новой функциональности."""
    
    def test_something(self):
        """Описание теста."""
        # Arrange
        expected = "value"
        
        # Act
        result = some_function()
        
        # Assert
        assert result == expected
```

**2. Использовать фикстуры для повторяющихся данных:**
```python
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_with_fixture(sample_data):
    assert sample_data["key"] == "value"
```

**3. Параметризация тестов:**
```python
@pytest.mark.parametrize("input,expected", [
    ("test", "TEST"),
    ("hello", "HELLO"),
])
def test_upper(input, expected):
    assert input.upper() == expected
```

---

## Лучшие практики

**1. Изоляция тестов:**
- Каждый тест должен быть независимым
- Использовать `tempfile` для временных файлов
- Использовать `mock.patch` для изоляции от внешних зависимостей

**2. Именование:**
- Классы: `TestClassName`
- Методы: `test_method_name_scenario`
- Файлы: `test_module_name.py`

**3. Структура теста (AAA):**
```python
def test_something():
    # Arrange - подготовка данных
    data = prepare_data()
    
    # Act - выполнение действия
    result = function_under_test(data)
    
    # Assert - проверка результата
    assert result == expected
```

**4. Документация:**
- Каждый тест должен иметь docstring с описанием
- Описание должно быть понятным без чтения кода

**5. Покрытие:**
- Стремиться к покрытию > 80%
- Тестировать граничные случаи
- Тестировать обработку ошибок

---

## Примеры запуска

```bash
# Все тесты
make test

# Только тесты провайдеров
make test filter=test_providers.py

# Только тесты core модулей
make test filter=test_core.py

# Конкретный класс
pytest tests/test_providers.py::TestDeepSeekProvider -v

# С покрытием
pytest tests/ --cov=aider --cov-report=term-missing

# С подробным выводом
pytest tests/ -vv

# Остановка на первой ошибке
pytest tests/ -x

# Показать локальные переменные при ошибке
pytest tests/ -l
```

---

## Статистика тестов

**Всего тестов:** 32

**По модулям:**
- test_providers.py: 19 тестов
- test_core.py: 13 тестов

**По компонентам:**
- DeepSeekProvider: 6 тестов
- AnthropicProvider: 4 теста
- ChatGPTProvider: 4 теста
- LLMProviderFactory: 5 тестов
- TaskManager: 8 тестов
- LogManager: 5 тестов

**Время выполнения:** ~0.5-0.8 секунд

**Покрытие кода:** ~85% (провайдеры и core модули)
