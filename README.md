# The Foundry

Оркестратор «agentic feature pipeline»: GitHub issue → план → реализация → верификация → PR. Каждая задача проходит линейный FSM (`fetch → context → plan → implement → verify → pr → done`), исполняется в собственном git-worktree и пишет append-only лог событий в SQLite. Сверху живёт FastAPI + React UI с лайв-стримом (SSE) того, что делает агент.

Проект сделан в рамках **Hacker Sprint #1: Фабрика фичей** ([Notion](https://www.notion.so/Hacker-Sprint-1-33f2db4c860e8064a657e199b4578f66?source=copy_link)).

> **TL;DR.** Поставь зависимости (`uv sync`, `cd web && npm install`), скопируй `.env.example` → `.env`, заполни `SOURCE_REPO`/`TARGET_REPO`, и запускай три процесса в трёх терминалах: **listener** (`uv run foundry run`), **API** (`uv run uvicorn api.main:app --reload`), **UI** (`cd web && npm run dev`). Или одной командой в Docker: `docker compose up --build`. По умолчанию listener гоняет stub-агента (оффлайн); чтобы получить реальный код от LLM, поставь `claude` CLI и переключи `CODING_AGENT=claude_cli`.

---

## Содержание

- [Что внутри](#что-внутри)
- [Подготовка окружения](#подготовка-окружения)
- [Конфигурация (`.env`)](#конфигурация-env)
- [Запуск: три раннера](#запуск-три-раннера)
- [Docker-запуск](#docker-запуск)
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

Подробнее по слоям — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) и [DEBUG.md](DEBUG.md) (verified runbook).

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
BASE_BRANCH=main
ISSUE_LABEL=agent-task
# Optional: narrow or split the queue without changing code.
# ISSUE_LABELS=agent-task,queue/backend
# ISSUE_ASSIGNEE=octocat
# ISSUE_MILESTONE=v1
# ISSUE_LIMIT=50

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

### Прогон на `podlodka-ai-club/the-foundry`

Для dogfood-прогона на реальном репозитории можно использовать тот же репозиторий как источник issue и цель PR. Создай отдельный лейбл, чтобы listener не забрал случайные issue:

```bash
gh label create foundry-task --repo podlodka-ai-club/the-foundry --color 5319e7 || true
```

Минимальный `.env`:

```bash
SOURCE_REPO=podlodka-ai-club/the-foundry
TARGET_REPO=podlodka-ai-club/the-foundry
BASE_BRANCH=main
ISSUE_LABEL=foundry-task
CODING_AGENT=codex_cli
AGENT_MODEL=gpt-5
AGENT_TIMEOUT_SEC=900
AGENT_MAX_TURNS=20
AGENT_IMPLEMENT_MAX_TURNS=40
VERIFY_COMMANDS=[["uv","run","ruff","check","."],["uv","run","pytest","-x","--no-header","-q"],["npm","--prefix","web","ci"],["npm","--prefix","web","run","build"],["npm","--prefix","web","run","lint"]]
```

Дальше заведи небольшое issue с лейблом `foundry-task` и запусти один проход:

```bash
uv run foundry run-issue <issue-number>
# или, если хочешь проверить polling-фильтры:
uv run foundry run --once
```

`BASE_BRANCH` используется и для синхронизации `_base`, и для `git worktree add`, и как `--base` при создании PR. Если default branch проекта переименуют, достаточно поменять одну переменную.

### Безопасность и rollback

Foundry изолирует каждую задачу в отдельный git worktree, но это не полноценная security sandbox. Реальные CLI-агенты умеют запускать shell-команды, читать доступные им файлы и пользоваться переданными им credentials. Поэтому дефолт теперь консервативный:

- `SAFE_AGENT_MODE=true` по умолчанию: Claude запускается без `--dangerously-skip-permissions`, Codex — без `--dangerously-bypass-approvals-and-sandbox`;
- `CODEX_SANDBOX_MODE` можно использовать для явного режима Codex sandbox (`read-only`, `workspace-write`, `danger-full-access`); в Docker Compose по умолчанию стоит `danger-full-access`, потому что bubblewrap/user namespace sandbox часто недоступен внутри контейнера (`bwrap: No permissions to create a new namespace`), а внешней границей изоляции выступает сам контейнер;
- env для agent subprocess scrubbed: передаются только базовые runtime-переменные (`PATH`, `HOME`, `SSH_AUTH_SOCK`, locale и т.п.), backend auth key и явный `AGENT_ENV_ALLOWLIST`;
- собственные shell-вызовы Foundry проходят denylist для `rm -rf`, `git push --force`, `git checkout main` в task worktree и `git reset --hard` вне task worktree;
- перед каждой новой implement-попыткой сохраняется `git diff --binary HEAD` в `data/checkpoints/`, а retry делает `git reset --hard HEAD` внутри task worktree перед новой попыткой;
- failed task worktree не удаляется автоматически: его можно открыть и забрать полезный diff руками.

Текущие ограничения: shell denylist защищает только команды, которые идут через Foundry wrapper. В safe mode безопасность внутренних shell-вызовов Claude/Codex опирается на permission/sandbox-механизмы самих CLI. Если выставить `SAFE_AGENT_MODE=false`, Foundry снова передаст опасные bypass-флаги; делай это только в одноразовом sandbox-репозитории без ценных секретов.

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
uv run foundry pr-feedback --once        # один проход по review/CI feedback в открытых PR
```

Каждый проход: `fetch labeled issues → context → plan → implement → verify → pr` для каждой задачи. Результат каждой стадии пишется в `task_events` (SQLite) — UI читает оттуда. Дополнительные команды:

```bash
uv run foundry run-issue <number>        # ручной запуск одного issue без фильтров polling-очереди
uv run foundry status                    # таблица всех задач из БД
uv run foundry reset <task_id>           # вернуть задачу в PENDING/FETCH (для отладки)
```

Выборка issue остаётся простой: `foundry run` вызывает `gh issue list` по `SOURCE_REPO`, `ISSUE_LABELS`/`ISSUE_LABEL`, `ISSUE_ASSIGNEE`, `ISSUE_MILESTONE`, `ISSUE_LIMIT`, затем upsert'ит найденное в SQLite. Лейблы `priority/p0` и `priority/p1` только поднимают задачи выше внутри текущего прохода. Таблица SQLite `tasks` здесь фактически и есть очередь: pending/running-записи переживают рестарт и подхватываются следующим запуском.

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

## Docker-запуск

Docker Compose поднимает сразу три процесса:

| Сервис | Что запускает | Порт |
| --- | --- | --- |
| `api` | FastAPI backend (`uvicorn api.main:app`) | `8000` |
| `worker` | listener / pipeline (`foundry run`) | — |
| `web` | Vite UI с прокси на `api:8000` | `5173` |

Минимальный запуск:

```bash
cp .env.example .env
$EDITOR .env                              # заполнить SOURCE_REPO / TARGET_REPO
docker compose up --build
```

После старта UI доступен на http://localhost:5173, API — на http://localhost:8000. SQLite и worktree'ы остаются на хосте в `./data` и `./worktrees`, чтобы их можно было смотреть обычными локальными инструментами.

Compose монтирует локальный `gh` auth из `${HOME}/.config/gh`. Для git-коммитов внутри контейнера по умолчанию используется `Foundry Bot <foundry@example.local>`; при желании переопредели `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` в `.env`. Если хочешь вместо stub включить реальный coding backend, выставь в `.env` нужный `CODING_AGENT` и раскомментируй соответствующий auth-volume в `docker-compose.yml`:

```yaml
# Claude Code
- ${HOME}/.claude:/root/.claude

# Codex CLI
- ${HOME}/.codex:/root/.codex

# OpenCode
- ${HOME}/.local/share/opencode:/root/.local/share/opencode
```

Образ backend'а включает Node 24 и умеет опционально ставить CLI-агенты на этапе build. Разово:

```bash
INSTALL_CLAUDE_CLI=true docker compose build api worker
INSTALL_CODEX_CLI=true docker compose build api worker
INSTALL_OPENCODE_CLI=true docker compose build api worker
```

Для постоянного режима можно положить нужный флаг в `.env`, чтобы `docker compose up --build` тоже собирал образ с этим CLI. Если CLI уже лежит в собственном кастомном образе или используется только `CODING_AGENT=stub`, эти флаги не нужны.

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
uv run pytest                            # 193 tests, оффлайн
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

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — каноническая архитектура: workflow, stages, agents, API/UI, безопасность.
- [DEBUG.md](DEBUG.md) — verified runbook: локальный запуск, быстрые probes, тесты, отладка SQLite/workflows.
- [docs/specs/observability-ui.md](docs/specs/observability-ui.md) — актуальный контракт observability/API/UI слоя.
- [IDEAS.md](IDEAS.md) — свалка будущих направлений (как есть, без додумывания).
- [design_handoff_foundry_observability/](design_handoff_foundry_observability/) — hi-fi дизайн-референс UI.
