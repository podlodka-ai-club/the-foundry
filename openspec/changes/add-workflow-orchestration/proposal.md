## Why

Сейчас оркестратор — это один линейный поток `fetch -> context -> plan -> implement -> verify -> pr`. Для MVP этого достаточно, но retry-циклы, отдельная проверка PR, отмена, диалоговые режимы и будущая маршрутизация событий быстро превратят `pipeline.py` в набор неявных веток.

Нужен явный workflow-слой: достаточно маленький, чтобы не тащить преждевременно LangGraph, но достаточно формальный, чтобы поддержать quality gates, разные входные события и будущие режимы вроде декомпозиции, code review и deploy.

## What Changes

- Добавить модель workflow orchestration: именованные workflow, шаги, результаты шагов и отдельные entrypoint'ы.
- Перенести существующий issue-driven путь в workflow `dev_task` без изменения публичного поведения `foundry run`.
- Добавить ограниченный цикл `implement -> verify -> implement` внутри `dev_task`.
- Сделать результат verifier'а структурированным: pass, retryable fail, terminal fail, needs human, infra fail.
- Добавить отдельный workflow `pr_verify`, который проверяет уже существующий PR/worktree-контекст и пишет PR-facing отчёт, а не открывает новый PR.
- Сохранить `task_events` как основной источник правды для UI: старты, завершения, ошибки, попытки, входы/выходы агентов, стоимость.
- Зафиксировать принцип для будущего agentic planner: агент может предлагать typed outcome (`plan_ready`, `needs_input`, `declined`, `decompose`), но orchestrator исполняет только разрешённые системные переходы.

## Capabilities

### New Capabilities
- `workflow-orchestration`: описывает, как Foundry представляет, маршрутизирует, запускает, возобновляет и наблюдает именованные workflow вроде `dev_task` и `pr_verify`.
- `quality-gates`: описывает ограниченные implementation attempts, структурированную верификацию, retry-решения и PR verification reports.

### Modified Capabilities

Нет. В репозитории пока нет архивированных OpenSpec capabilities.

## Impact

- Код: `src/foundry/pipeline.py`, новые orchestration/workflow-модули под `src/foundry/`, `src/foundry/stages/verify.py`, тесты под `tests/`.
- API/UI: существующий контракт endpoints менять не требуется; `task_events` остаётся источником данных. Могут появиться новые поля payload для workflow name и attempt number.
- CLI: `foundry run` сохраняет текущее поведение для labeled issues. Для `pr_verify` можно добавить отдельный внутренний entrypoint или CLI-команду в последующей итерации.
- Dependencies: в первой итерации новых runtime-зависимостей не планируется. LangGraph остаётся вариантом на будущее, если локальный runner станет слишком сложным.
