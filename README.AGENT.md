- [О проекте](README.md)
- [Кодинг агент](#)

# Кодинг агент 

Скрипт для автономного запуска кодинг ИИ агентов: ``aider/agent.py`` в среде ``aider``.

## Установка

1. Установите зависимости:
```bash
pip install -e .
```

2. Скопируйте `.env.sample` в `.env` и заполните API ключи:
```bash
cp .env.sample .env
```

3. Отредактируйте `.env` файл, указав ваши API ключи для выбранной LLM.

## Использование AI-агента

Скрипт `aider/agent.py` позволяет автоматически выполнять задачи через AI-агента (aider).

### Примеры использования

**Создание новой задачи с промтом:**
```bash
python aider/agent.py --task="TF-2" --prompt="Напиши скрипт, выводящий в консоль 'Hello world'"
```

**Выполнение существующей задачи:**
```bash
python aider/agent.py --task="TF-1"
```

**Дополнение существующей задачи:**
```bash
python aider/agent.py --task="TF-2" --prompt="Добавь обработку исключений"
```

### Параметры

- `--task` (обязательный) - номер задачи (может содержать буквы, цифры и дефис)
- `--prompt` (необязательный) - текст задачи

### Структура файлов

- Файлы задач: `aider/tasks/<task_id>/<task_id>_task.md`
- Логи выполнения: `aider/tasks/<task_id>/<task_id>_log.md`
- Рабочая директория: `code/` (все изменения выполняются только здесь)

### Настройки LLM

В `.env` файле настройте используемую LLM:
```
CODING_LLM=DEEPSEEK
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

Поддерживаемые LLM: DEEPSEEK, ANTHROPIC, CHATGPT

## Запуск через Docker

Docker позволяет запускать агента без установки зависимостей локально. Все работает в изолированном контейнере.

### Предварительные требования

- Установленный Docker и Docker Compose
- Файл `.env` с настройками API ключей

### Сборка образа

```bash
docker-compose build
```

или через Makefile:

```bash
make build
```

### Запуск агента

**Создание новой задачи:**
```bash
docker-compose run --rm foundry-agent --task="TF-2" --prompt="Напиши скрипт hello world"
```

**Выполнение существующей задачи:**
```bash
docker-compose run --rm foundry-agent --task="TF-1"
```

**Через Makefile:**
```bash
make runagent task=TF-2 prompt="Напиши скрипт hello world"
make runagent task=TF-1
```

### Дополнительные команды

**Открыть shell в контейнере:**
```bash
make shell
```

**Очистить Docker ресурсы:**
```bash
make clean
```

**Показать справку:**
```bash
make help
```

### Volumes (монтируемые директории)

- `./code` → `/app/code` - рабочая директория для изменений
- `./aider/tasks` → `/app/aider/tasks` - задачи и логи
- `./.env` → `/app/.env` (read-only) - конфигурация

Все изменения, сделанные агентом в `code/` и логи в `aider/tasks/`, сохраняются на хост-машине.

## Docs
Документы, логи встреч и прочие текстовые артефакты храним в папке `/docs`.


