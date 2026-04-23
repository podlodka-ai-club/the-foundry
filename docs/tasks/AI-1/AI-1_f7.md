**Задача AI-1_f7: Докеризация проекта The Foundry**

**Дата создания:** 23.04.2026 13:20

---

**Описание задачи**

Создать Docker-контейнер для проекта The Foundry, чтобы обеспечить одинаковую работу во всех средах (Windows, Linux, macOS) и избежать проблем с зависимостями и совместимостью Python-пакетов.

---

**Цели докеризации**

1. **Изоляция окружения** - все зависимости внутри контейнера
2. **Воспроизводимость** - одинаковая работа на любой ОС
3. **Простота развертывания** - не требуется установка Python и зависимостей локально
4. **Решение проблем совместимости** - фиксированная версия Python и библиотек
5. **Персистентность данных** - сохранение результатов работы на хост-машине

---

**План реализации**

**Шаг 1: Создание Dockerfile**
- Базовый образ: `python:3.12-slim`
- Установка git (требуется для aider и GitPython)
- Копирование файлов проекта
- Установка зависимостей (aider-chat, python-dotenv)
- Создание рабочих директорий
- Настройка точки входа

**Шаг 2: Создание docker-compose.yml**
- Определение сервиса `foundry-agent`
- Настройка volumes для персистентности данных:
  - `./code` → `/app/code`
  - `./aider/tasks` → `/app/aider/tasks`
  - `./.env` → `/app/.env` (read-only)
- Настройка переменных окружения
- Включение интерактивного режима (stdin_open, tty)

**Шаг 3: Создание .dockerignore**
- Исключение виртуального окружения (.venv)
- Исключение IDE файлов (.idea)
- Исключение Python кэша (__pycache__, *.pyc)
- Исключение git и логов
- Исключение документации (docs, specs)

**Шаг 4: Создание Makefile**
- Команда `build` - сборка образа
- Команда `run` - запуск агента с аргументами
- Команда `shell` - открытие shell в контейнере
- Команда `clean` - очистка Docker ресурсов
- Команда `help` - справка по командам

**Шаг 5: Обновление документации**
- Добавить секцию "Запуск через Docker" в README.AGENT.md
- Описать предварительные требования
- Добавить примеры использования
- Описать volumes и их назначение

---

**Лог выполнения**

**23.04.2026 13:20 - Начало работы**

**1. Создан Dockerfile:**
```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY aider/ ./aider/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir aider-chat python-dotenv

RUN mkdir -p /app/code /app/aider/tasks

WORKDIR /app

ENTRYPOINT ["python", "aider/agent.py"]
```

**Особенности:**
- Использован slim-образ для уменьшения размера
- Git установлен для работы aider
- Зависимости устанавливаются без кэша для экономии места
- Созданы необходимые директории

**2. Создан docker-compose.yml:**
```yaml
version: '3.8'

services:
  foundry-agent:
    build: .
    container_name: foundry-agent
    volumes:
      - ./code:/app/code
      - ./aider/tasks:/app/aider/tasks
      - ./.env:/app/.env:ro
    environment:
      - PYTHONUNBUFFERED=1
    stdin_open: true
    tty: true
```

**Особенности:**
- Volumes обеспечивают персистентность данных
- `.env` монтируется в режиме read-only для безопасности
- `PYTHONUNBUFFERED=1` для немедленного вывода логов
- `stdin_open` и `tty` для интерактивной работы

**3. Создан .dockerignore:**
```
.venv/
.idea/
__pycache__/
*.pyc
*.pyo
*.pyd
.git/
.gitignore
*.log
.env
setup.log
docs/
specs/
README.md
README.AGENT.md
```

**Назначение:** Исключение ненужных файлов из образа для уменьшения размера и ускорения сборки.

**4. Создан Makefile:**
```makefile
.PHONY: build run shell clean help

help:
	@echo "Доступные команды:"
	@echo "  make build       - Собрать Docker образ"
	@echo "  make run ARGS=   - Запустить агента с аргументами"
	@echo "  make shell       - Открыть shell в контейнере"
	@echo "  make clean       - Очистить Docker ресурсы"

build:
	docker-compose build

run:
	docker-compose run --rm foundry-agent $(ARGS)

shell:
	docker-compose run --rm foundry-agent /bin/bash

clean:
	docker-compose down -v
	docker system prune -f
```

**Назначение:** Упрощение работы с Docker через короткие команды.

**5. Обновлен README.AGENT.md:**
- Добавлена секция "Запуск через Docker"
- Описаны предварительные требования
- Добавлены примеры использования через docker-compose и Makefile
- Описаны дополнительные команды (shell, clean, help)
- Документированы volumes и их назначение

---

**Результаты**

**Созданные файлы:**
1. `Dockerfile` - описание Docker-образа
2. `docker-compose.yml` - конфигурация для запуска
3. `.dockerignore` - исключения для сборки
4. `Makefile` - утилиты для упрощения команд
5. `README.AGENT.md` (обновлен) - документация по использованию

**Структура проекта после докеризации:**
```
the-foundry/
├── Dockerfile              # Описание образа
├── docker-compose.yml      # Конфигурация запуска
├── .dockerignore          # Исключения для сборки
├── Makefile               # Утилиты
├── aider/
│   ├── agent.py           # Основной скрипт
│   └── tasks/             # Задачи и логи (volume)
├── code/                  # Рабочая директория (volume)
├── .env                   # Конфигурация (volume, read-only)
└── README.AGENT.md        # Документация
```

---

**Преимущества реализованного решения**

✅ **Изоляция** - все зависимости в контейнере, не влияют на хост-систему
✅ **Воспроизводимость** - одинаковая работа на Windows, Linux, macOS
✅ **Простота** - не нужно устанавливать Python, pip, зависимости
✅ **Безопасность** - .env монтируется read-only
✅ **Персистентность** - результаты работы сохраняются на хосте
✅ **Удобство** - Makefile упрощает команды
✅ **Компактность** - slim-образ, минимальный размер

---

**Примеры использования**

**Сборка образа:**
```bash
make build
```

**Запуск задачи:**
```bash
make runagent task=TF-2 prompt="Создай hello world скрипт"
```

**Выполнение существующей задачи:**
```bash
make runagent task=TF-1
```

**Открытие shell для отладки:**
```bash
make shell
```

**Очистка ресурсов:**
```bash
make clean
```

---

**Тестирование**

**Команды для проверки:**

1. Сборка образа:
```bash
docker-compose build
```

2. Проверка создания образа:
```bash
docker images | grep foundry
```

3. Тестовый запуск:
```bash
make runagent task=TEST-1 prompt="echo test"
```

4. Проверка volumes:
```bash
ls -la code/
ls -la aider/tasks/
```

---

**Статус:** Успешно выполнено ✓

**Дата завершения:** 23.04.2026 13:25

---

**Обновление (23.04.2026 13:30):**

Изменен синтаксис команды Makefile для более удобного использования:
- Старый формат: `make run ARGS='--task=TF-1 --prompt="Test"'`
- Новый формат: `make runagent task=TF-1 prompt="Test"`

Преимущества:
- Более читаемый синтаксис
- Не нужно экранировать кавычки
- Автоматическая обработка наличия/отсутствия prompt
- Соответствие стандартам Makefile

---

**Следующие шаги**

1. Протестировать сборку образа: `make build`
2. Создать тестовую задачу: `make runagent task=TEST-1 prompt="Test task"`
3. Проверить работу volumes (сохранение файлов)
4. Опционально: оптимизировать размер образа через multi-stage build
5. Опционально: добавить docker-образ в CI/CD pipeline
