# Skeleton end-to-end — что сделано

End-to-end скелет пайплайна с заглушками вместо LLM (фаза «Дни 1–2» из [architecture/draft.md](architecture/draft.md)).
План реализации — [architecture/bubbly-skipping-mccarthy.md](architecture/bubbly-skipping-mccarthy.md).

## Что сделано

- **Конфиг/модели/стейт**: [../pyproject.toml](../pyproject.toml), [../.env.example](../.env.example), [../.gitignore](../.gitignore), [../src/foundry/config.py](../src/foundry/config.py), [../src/foundry/models.py](../src/foundry/models.py), [../src/foundry/state.py](../src/foundry/state.py) (SQLite CRUD + logs).
- **Инфра**: [../src/foundry/shell.py](../src/foundry/shell.py) (обёртка subprocess), [../src/foundry/worktree.py](../src/foundry/worktree.py) (git worktree через `gh`/`git`).
- **Стадии**: [fetch.py](../src/foundry/stages/fetch.py) (реальный `gh issue list`), [context.py](../src/foundry/stages/context.py) / [plan.py](../src/foundry/stages/plan.py) / [implement.py](../src/foundry/stages/implement.py) / [verify.py](../src/foundry/stages/verify.py) — STUB'ы, [pr.py](../src/foundry/stages/pr.py) — реальный commit/push/`gh pr create`.
- **FSM**: [../src/foundry/pipeline.py](../src/foundry/pipeline.py) с сохранением стадии после каждого шага и graceful-обработкой падений.
- **CLI**: [../src/foundry/cli.py](../src/foundry/cli.py) — `foundry run | status | reset <id>`.
- **Тесты**: [../tests/test_state.py](../tests/test_state.py), [../tests/test_pipeline.py](../tests/test_pipeline.py) — **6/6 passed**, CLI `--help` работает.

## Что нужно сделать вручную до первого прогона

1. `brew install uv gh` — ни `uv`, ни `gh` не установлены.
2. `gh auth login` — токен с правом `repo`.
3. Создать на GitHub sandbox-репо (например `the-foundry-sandbox`), лейбл `agent-task`, 1–2 issue.
4. `cp .env.example .env` и заполнить `GITHUB_TOKEN`, `SOURCE_REPO`, `TARGET_REPO`.
5. `uv sync && uv run foundry run` — ожидаемый результат: в sandbox появился PR с новой строкой в README.

## Observability & UI

Поверх пайплайна добавлен observability-слой: append-only таблица `task_events` (запись через `record_event` и `stage_span` в [../../src/foundry/events.py](../../src/foundry/events.py)), FastAPI-эндпоинты в [../../src/api/](../../src/api/) (`/api/tasks`, `/api/tasks/{id}`, SSE на `/api/tasks/{id}/events`) и фронт на Vite/React в [../../web/](../../web/). UI поллит список каждые 3 сек и подписывается на SSE для раскрытой задачи; SSE реализован как polling SQLite, потому что pipeline и uvicorn — разные процессы. Канонические документы этого слоя — [../specs/observability-ui.md](../specs/observability-ui.md) и [../specs/observability-ui-plan.md](../specs/observability-ui-plan.md).
