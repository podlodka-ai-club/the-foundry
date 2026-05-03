# The Foundry

Оркестратор «agentic feature pipeline»: GitHub issue → план → реализация → верификация → PR. Каждая задача проходит линейный FSM (`fetch → context → plan → implement → verify → pr → done`), исполняется в собственном git-worktree и пишет append-only лог событий в SQLite. Сверху живёт FastAPI + React UI с лайв-стримом (SSE) того, что делает агент.

Проект сделан в рамках **Hacker Sprint #1: Фабрика фичей** ([Notion](https://www.notion.so/Hacker-Sprint-1-33f2db4c860e8064a657e199b4578f66?source=copy_link)).

> **TL;DR.** Поставь зависимости (`uv sync`, `cd web && npm install`), скопируй `.env.example` → `.env`, заполни `SOURCE_REPO`/`TARGET_REPO`, и запускай три процесса в трёх терминалах: **listener** (`uv run foundry run`), **API** (`uv run uvicorn api.main:app --reload`), **UI** (`cd web && npm run dev`). По умолчанию listener гоняет stub-агента (оффлайн); чтобы получить реальный код от LLM, поставь `claude` CLI и переключи `CODING_AGENT=claude_cli`.

---

## Содержание

- [Что внутри](#что-внутри)
- [Подготовка окружения](#подготовка-окружения)
- [Конфигурация (`.env`)](#конфигурация-env)
- [Запуск: три раннера](#запуск-три-раннера)
- [Smoke-прогон](#smoke-прогон)
- [Тесты](#тесты)
- [Документация](#документация)

---

## Что внутри

| Компонент | Где живёт | Что делает |
| --- | --- | --- |
| **Listener / pipeline** | [src/foundry/](src/foundry/) (entrypoint `foundry` CLI) | Поллит GitHub issue с заданным лейблом, прогоняет каждый через стадии, открывает PR и закрывает issue. Состояние — SQLite. |
| **Coding agents** | [src/foundry/agents/](src/foundry/agents/) | Pluggable backends для стадий `plan`/`implement`/`verify`: `stub` (оффлайн, по умолчанию), `claude_cli`, `codex_cli`, `opencode_cli`. |
| **HTTP API** | [src/api/](src/api/) (FastAPI на `:8000`) | `/api/tasks`, `/api/tasks/{id}`, SSE на `/api/tasks/{id}/events`, `/api/repos`. |
| **Web UI** | [web/](web/) (Vite + React + TS на `:5173`) | Список задач, раскрывающаяся карточка со stepper'ом и потоком событий агента. |

Подробнее по слоям — [CLAUDE.md](CLAUDE.md) (project map), [docs/architecture/skeleton.md](docs/architecture/skeleton.md) и [DEBUG.md](DEBUG.md) (verified runbook).

---

## Подготовка окружения

**Обязательные инструменты в PATH:**

```bash
brew install uv gh node                  # uv, gh, Node.js
gh auth login                            # токен с правом `repo`
```

**Опционально — реальный coding-агент** (если хочешь, чтобы план/имплементацию писала LLM, а не stub):

```bash
# Anthropic Claude CLI (https://docs.claude.com/en/docs/claude-code/setup)
brew install --cask claude
claude /login                            # OAuth подписки или ANTHROPIC_API_KEY
```

**GitHub-стороны** (один или два репозитория — могут совпадать):

1. Sandbox-репо для issue (`SOURCE_REPO`). Пример: `your-org/the-foundry-sandbox`.
2. Лейбл для тегирования задач (по умолчанию `agent-task`).
3. Репо, в который пушим PR (`TARGET_REPO`). Чаще всего тот же, что и `SOURCE_REPO`.

---

## Конфигурация (`.env`)

```bash
cp .env.example .env
$EDITOR .env
```

Минимальные обязательные поля — `SOURCE_REPO` и `TARGET_REPO`. Без них любая команда `foundry` падает с `config error`.

### Живой пример: pipeline на Claude Code

Stub-режим хорош для smoke-теста (оффлайн, детерминирован: добавляет строку в `README.md`), но для реального прогона проще всего взять `claude` CLI:

```bash
# .env

SOURCE_REPO=your-org/the-foundry-sandbox
TARGET_REPO=your-org/the-foundry-sandbox
ISSUE_LABEL=agent-task

# Coding agent — Claude CLI на подписке (OAuth) или ANTHROPIC_API_KEY
CODING_AGENT=claude_cli
AGENT_MODEL=sonnet                 # haiku | sonnet | opus | <full id>
AGENT_MAX_TURNS=20
AGENT_TIMEOUT_SEC=600

# Хочется быстрее на planning/verify, но мощнее на implement?
AGENT_PLAN_MODEL=haiku
AGENT_VERIFY_MODEL=haiku
AGENT_IMPLEMENT_MODEL=sonnet
AGENT_IMPLEMENT_MAX_TURNS=40
```

Все доступные ключи и оверрайды задокументированы в [.env.example](.env.example) (в т.ч. `codex_cli`, `opencode_cli` и опциональный Langfuse-трейсинг).

### Живой пример: pipeline на OpenCode + DeepSeek

Если нет подписки на Claude и не хочется тратить кредиты Anthropic API — есть путь через [OpenCode](https://opencode.ai/) (CLI-агент, умеющий ходить в десятки провайдеров) и DeepSeek (дешёвый API-ключ, регистрация на [platform.deepseek.com](https://platform.deepseek.com/)).

Prereqs:

```bash
# 1. Поставить opencode CLI
curl -fsSL https://opencode.ai/install | bash
# либо: brew install anomalyco/tap/opencode
# либо: npm install -g opencode-ai

# 2. Положить DeepSeek API key в auth.json (формат документирован в opencode docs)
mkdir -p ~/.local/share/opencode
cat > ~/.local/share/opencode/auth.json <<'EOF'
{
  "deepseek": { "type": "api", "key": "sk-..." }
}
EOF

# 3. Smoke-проверка — должен ответить без TUI
opencode run -m deepseek/deepseek-v4-flash "say hi in one word"
```

Полный список поддерживаемых провайдеров и моделей — [opencode.ai/docs/providers](https://opencode.ai/docs/providers/).

`.env`:

```bash
SOURCE_REPO=your-org/the-foundry-sandbox
TARGET_REPO=your-org/the-foundry-sandbox
ISSUE_LABEL=agent-task

# Coding agent — opencode + DeepSeek
CODING_AGENT=opencode_cli
AGENT_MODEL=deepseek/deepseek-v4-flash   # дешёвый дефолт, аналог haiku
AGENT_MAX_TURNS=20
AGENT_TIMEOUT_SEC=600

# Per-stage: на implement берём более сильную модель
AGENT_PLAN_MODEL=deepseek/deepseek-v4-flash
AGENT_VERIFY_MODEL=deepseek/deepseek-v4-flash
AGENT_IMPLEMENT_MODEL=deepseek/deepseek-v4-pro
AGENT_IMPLEMENT_MAX_TURNS=40
```

Аутентификация и формат идентификатора модели — на стороне `opencode` CLI; foundry-бэкенд только пробрасывает `-m <model>` и `--session <id>` для resume. Поэтому смену провайдера (DeepSeek → OpenAI → локальный Ollama → …) делаешь правкой `auth.json` + `AGENT_MODEL`, без изменений в коде.

> **Важно про observability:** в отличие от `claude_cli`, бэкенд `opencode_cli` пока не стримит инкрементальные `agent_tool` / `agent_text` события в `task_events` — UI увидит только финальный `stage_finished` (см. TODO в [src/foundry/agents/opencode_cli.py](src/foundry/agents/opencode_cli.py)).

---

## Запуск: три раннера

UI и листенер — **разные процессы**, читающие одну и ту же SQLite. Запускай каждый в своём терминале (или в `tmux`/Process Compose).

### 1. Listener (pipeline)

```bash
uv run foundry run                       # бесконечный polling-режим
uv run foundry run --once                # одиночный проход и выход
uv run foundry run --interval 10         # переопределить POLL_INTERVAL_SECONDS
```

Каждый проход: `fetch labeled issues → context → plan → implement → verify → pr` для каждой задачи. Результат каждой стадии пишется в `task_events` (SQLite) — UI читает оттуда. Дополнительные команды:

```bash
uv run foundry status                    # таблица всех задач из БД
uv run foundry reset <task_id>           # вернуть задачу в PENDING/FETCH (для отладки)
```

### 2. Backend API (FastAPI)

```bash
uv run uvicorn api.main:app --reload     # http://localhost:8000
```

Эндпоинты: `GET /api/tasks`, `GET /api/tasks/{id}`, `GET /api/tasks/{id}/events` (SSE, поддерживает `Last-Event-ID`), `GET /api/repos`. Health: `GET /`.

### 3. Web UI

```bash
cd web && npm install                    # один раз
npm run dev                              # http://localhost:5173
```

Vite-прокси перебрасывает `/api` → `http://localhost:8000` — пока порт API не двигаешь, ничего больше править не нужно. Тёмная тема — по умолчанию, светлая включается через системное `prefers-color-scheme` или вручную: `<html data-theme="light">`.

---

## Smoke-прогон

Самый быстрый способ убедиться, что всё работает:

```bash
# 1. listener в одном терминале
uv run foundry run --once

# 2. в другом терминале — создать issue + дождаться, пока его подхватят
scripts/add-and-process.sh
```

[`scripts/add-and-process.sh`](scripts/add-and-process.sh) создаёт issue в `SOURCE_REPO`, ждёт появления его в `gh issue list --label`, и зовёт `foundry run`. Ожидаемый результат: в `TARGET_REPO` появился PR с новой строкой в `README.md` (если `CODING_AGENT=stub`) или с реальной реализацией (если `CODING_AGENT=claude_cli`).

---

## Тесты

```bash
uv run pytest                            # 134 passed (~3s, оффлайн)
uv run pytest tests/test_pipeline.py -v
```

Все внешние вызовы (`gh`, git, claude CLI) замоканы — тесты не ходят в сеть и не плодят worktree'ы.

Для фронта:

```bash
cd web
npx tsc --noEmit                         # strict TS типы
npm run build                            # tsc -b && vite build
```

---

## Документация

**Точка входа:**

- [docs/architecture/overview.md](docs/architecture/overview.md) — mermaid-схемы: поток данных listener → run → агент, граф зависимостей модулей, FSM run-а, таблица `workspace`-режимов.
- [docs/architecture/extending.md](docs/architecture/extending.md) — пошагово: как добавить новый **listener** и новую **automation** (включая выбор `workspace`, `session_key`, тесты).
- [CLAUDE.md](CLAUDE.md) — карта проекта для агентов и людей: архитектура, конвенции, правила.
- [DEBUG.md](DEBUG.md) — verified runbook: REPL, eval через `uv run python -c`, инспекция SQLite.

**Журналы рефакторингов и спецификации:**

- [docs/architecture/automations-roadmap.md](docs/architecture/automations-roadmap.md) — исторический roadmap C1–C6.
- [docs/architecture/simplify-2026-05.md](docs/architecture/simplify-2026-05.md) — последняя упрощающая итерация (kill `AgentStage`, единый `workspace`, выделение `runner.py`).
- [docs/architecture/pr-review-automation.md](docs/architecture/pr-review-automation.md), [docs/architecture/telegram-listener.md](docs/architecture/telegram-listener.md) — заметки по конкретным автоматизациям.
- [docs/architecture/agent-protocol.md](docs/architecture/agent-protocol.md) — исторический документ (≤ C2). Текущий контракт агента — в [src/foundry/agents/CLAUDE.md](src/foundry/agents/CLAUDE.md).
- [IDEAS.md](IDEAS.md) — свалка будущих направлений.
