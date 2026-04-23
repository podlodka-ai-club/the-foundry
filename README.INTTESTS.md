- [О проекте](README.md)
- [Кодинг агент](README.AGENT.md)
- [Unit Тесты](README.TESTS.md)
- [Интеграционные тесты](#)

# Интеграционные тесты

## Описание

Интеграционные тесты проверяют работу LLM агента end-to-end, выполняя реальные вызовы к API LLM провайдеров (DeepSeek, Anthropic, ChatGPT).

**Важно:** Эти тесты медленные (2-5 минут на тест) и требуют:
- Настроенный `.env` с API ключами
- Доступ к LLM API
- Docker для запуска агента

## Структура тестов

### Файл: `tests/test_integration.py`

**Тест №1: `test_create_current_dt_script`**
- Удаляет файл `code/current_dt.py`
- Выполняет `make runagent task=TF-1`
- Проверяет создание файла `code/current_dt.py`
- Запускает скрипт и проверяет вывод текущей даты/времени

**Тест №2: `test_modify_hello_script`**
- Создает файл `code/hello.py` с базовым содержимым
- Выполняет `make runagent task=TF-2`
- Запускает скрипт с вводом имени "Test"
- Проверяет вывод приветствия "Hello, Test!"

## Запуск тестов

### Все тесты (unit + integration)
```bash
make test
```

### Только unit тесты (быстрые, без LLM)
```bash
make test-unit
```

### Только интеграционные тесты (медленные, с LLM)
```bash
make test-int
```

### Конкретный интеграционный тест
```bash
pytest tests/test_integration.py::TestLLMIntegration::test_create_current_dt_script -v
```

## Требования

### 1. Настройка .env

Создайте файл `.env` на основе `.env.sample`:

```bash
cp .env.sample .env
```

Заполните API ключи:

```env
# DeepSeek
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_MODEL_NAME=deepseek/deepseek-chat

# Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL_NAME=claude-3-5-sonnet-20241022

# ChatGPT
CHATGPT_API_KEY=sk-your-key-here
CHATGPT_MODEL_NAME=gpt-4
```

### 2. Docker

Убедитесь, что Docker запущен:

```bash
docker --version
docker-compose --version
```

### 3. Собранный образ

Соберите Docker образ перед запуском тестов:

```bash
make build
```

## Ожидаемые результаты

### Успешный запуск

```bash
$ make test-int

============================= test session starts ==============================
platform linux -- Python 3.10.12, pytest-8.4.1, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /path/to/the-foundry
configfile: pytest.ini
plugins: anyio-4.12.1, asyncio-1.3.0, cov-7.0.0
collected 2 items

tests/test_integration.py::TestLLMIntegration::test_create_current_dt_script PASSED [ 50%]
tests/test_integration.py::TestLLMIntegration::test_modify_hello_script PASSED [100%]

============================== 2 passed in 245.67s (0:04:05) ==============================
```

### Пример вывода test_create_current_dt_script

```bash
$ python code/current_dt.py
2026-04-23 22:26:45
```

### Пример вывода test_modify_hello_script

```bash
$ python code/hello.py
What is your name? Test
Hello, Test!
```

## Отладка

### Просмотр логов агента

Логи сохраняются в `agent/tasks/TF-X/TF-X_log.md`:

```bash
cat agent/tasks/TF-1/TF-1_log.md
cat agent/tasks/TF-2/TF-2_log.md
```

### Запуск агента вручную

```bash
make runagent task=TF-1
make runagent task=TF-2
```

### Проверка созданных файлов

```bash
cat code/current_dt.py
cat code/hello.py
```

## Troubleshooting

### Ошибка: API ключ не найден

```
ValueError: DEEPSEEK_API_KEY not found in environment
```

**Решение:** Проверьте файл `.env`, убедитесь, что API ключ указан.

### Ошибка: Docker не запущен

```
Error response from daemon: ...
```

**Решение:** Запустите Docker Desktop.

### Ошибка: Timeout

```
subprocess.TimeoutExpired: Command '...' timed out after 120 seconds
```

**Решение:** Увеличьте timeout в тесте или проверьте доступность LLM API.

### Тест падает: файл не создан

```
AssertionError: Файл current_dt.py не был создан
```

**Решение:** 
1. Проверьте лог агента: `cat agent/tasks/TF-1/TF-1_log.md`
2. Убедитесь, что LLM API доступен
3. Проверьте, что задача TF-1 существует: `cat agent/tasks/TF-1/TF-1_task.md`

## Маркеры pytest

Интеграционные тесты помечены маркером `@pytest.mark.integration`.

Это позволяет запускать их отдельно:

```bash
# Только интеграционные
pytest -m integration

# Все кроме интеграционных
pytest -m "not integration"
```

## CI/CD

В CI/CD рекомендуется:
1. Запускать unit тесты на каждый commit
2. Запускать интеграционные тесты только на main/develop ветках
3. Использовать секреты для API ключей

Пример GitHub Actions:

```yaml
- name: Run unit tests
  run: make test-unit

- name: Run integration tests
  if: github.ref == 'refs/heads/main'
  env:
    DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
  run: make test-int
```
