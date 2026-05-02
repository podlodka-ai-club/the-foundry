# Automations roadmap (MVP)

Переход от статичного pipeline'а (`fetch → context → plan → implement → verify → pr` для одного типа задачи — GitHub issue) к **фабрике автоматизаций**: триггеры порождают события, автоматизации подписываются на события, агент сам оркестрирует через MCP — sub-агенты + skills.

Этот документ — master plan для шести инкрементальных шагов (C1…C6). Внутри каждого блока — design decisions, зафиксированные в обсуждении 2026-05-02, чтобы не утекли. Один блок = один change = один merge'аемый шаг, после которого репо в рабочем состоянии.

## Контекст

**Сегодня** (см. [skeleton.md](skeleton.md), [agent-protocol.md](agent-protocol.md), [../../CLAUDE.md](../../CLAUDE.md)):
- `pipeline.run_once()` — батч: `fetch.py` опрашивает GitHub-issues по label, для каждой запускается жёстко зашитый workflow `dev_task` ([src/foundry/workflows.py](../../src/foundry/workflows.py)).
- Стадии (`context → plan → implement↔verify → pr`) — модули в [src/foundry/stages/](../../src/foundry/stages/), вызываются Python-кодом по фиксированному порядку.
- Агенты pluggable ([src/foundry/agents/](../../src/foundry/agents/)) — `stub`, `claude_cli`, `codex_cli`, `opencode_cli` — но оркестрирует Python, не агент.
- `task_events` (append-only SQLite) — single source of truth для UI; `tasks.logs_json` — диагностический дневник.
- UI: `src/api/` (FastAPI) + `web/` (React + Vite) — Variant A (3 колонки), читает `/api/tasks` + SSE `/api/tasks/:id/events`.

**Целевая картина:**
- **Triggers** — long-running listeners (GitHub-poll, Discord, cron, webhook). Каждый эмиттит `Event { external_id, kind, payload, source }`. Если на event никто не подписан — он nowhere не сохраняется.
- **Automations** — декларативные `(triggers[OR], agent, prompt, skills[])`. На событие создаётся `Run`. `session_id = f(event.external_id, automation_id, agent_type)` — детерминирована, повторные events из того же канала продолжают тот же агентский диалог.
- **Sub-агенты через MCP** — top-level агент сам решает кого звать (никаких pre-defined фаз). Видит только финальный response саб-агента. UI разворачивает полное дерево через `parent_event_seq`.
- **Skills** — все side-effects (worktree, открыть PR, react, reply, compact context) — MCP tools. Per-automation access list.
- **UI** — Variant B (две колонки) в claude.app-стилистике, табы `Automations / Runs / Inbox`, дерево вызовов с раскрывающимися sub-agents и `mark_milestone` divider'ами. Мокапы: [`design_handoff_foundry_observability/project/Foundry Automations.html`](../../design_handoff_foundry_observability/project/Foundry%20Automations.html) (v2).

## Зафиксированные design decisions

Эти решения уже приняты, не пересматриваем без явной причины:

- **`mark_milestone` — это skill в дереве вызовов, а НЕ отдельный rail в шапке.** Top-level агент сам решает звать ли его. Никаких `expected_milestones` в automation-конфиге.
- **Top-level агент видит только final response sub-агента.** Полное поддерево пишется в `run_events` для UI и аудита, но не возвращается в LLM-контекст вызывающего.
- **`session_id` — pure function от `(external_id, automation_id, agent_type)`.** Конкретный алгоритм — открытый вопрос (см. ниже).
- **Sub-agent session ≠ top-level session.** При совпадении `(sub_agent_type, parent_session_id)` саб-агент получает ту же сессию (resume), иначе — новую.
- **Один listener эмиттит, никто не вызывает другой listener напрямую.** Если automation создаёт сущность (issue, task), это побочный эффект её skill'а (`open_github_issue`) — соответствующий listener подхватит как обычное внешнее событие.
- **`mark_milestone` рендерится как divider в дереве** ([`run-tree.jsx`](../../design_handoff_foundry_observability/project/automations-v2.jsx) `kind === 'mark'`).
- **Acknowledgement (✓ react в discord/github) — skill, который агент дёргает сам.** Не встроенное поведение orchestrator'а.
- **`failure_kind` словарь** (`deterministic` / `acceptance` / `infra` / `unclear` / `dangerous`) — UI лейблы: «Тесты/lint», «Не по задаче», «Инфра», «Непонятно», «Опасно». Хранится в БД как enum, рендерится по таблице.

## Шесть блоков

```
C1 (data model) ──┬─→ C2 (listeners) ──┐
                  ├─→ C3 (MCP server) ─┴─→ C4 (orchestrator) ─→ C5 (legacy) ─→ ✓
                  └─→ C6 (UI) ────────────────────────────────────────────────→ ✓
```

C2 и C3 — параллелятся. C6 (UI) можно начинать после C1 (есть данные), но реально показывать после C4.

---

### C1 — `add-event-and-automation-model` · фундамент данных

**Цель:** ввести модель `events` / `automations` / `runs`, без которой остальные блоки некуда писать.

**Deliverables:**
- Таблица `events` (`id`, `external_id`, `kind` enum, `source`, `payload` JSON, `parent_event_id`, `created_at`).
- Таблица `runs` (`id`, `automation_id`, `event_id`, `session_id`, `session_seq`, `status`, `started_at`, `duration_sec`, `cost_usd`, `failure_kind`, `failure_msg`, `waiting_reason`).
- Таблица `run_events` — переименование текущей `task_events` (`task_id` → `run_id`, добавить `parent_event_seq` для дерева вызовов).
- `Automation` dataclass + код-регистр в `src/foundry/automations/registry.py`. Поля: `id`, `name`, `description`, `triggers[]` (id триггеров), `agent` (backend + model), `prompt_path`, `skills[]`.
- `session_id = compute_session_id(external_id, automation_id, agent_type)` — функция-мост, конкретный алгоритм фиксируем здесь.
- Миграция: legacy `tasks` остаётся read-only (для архивных данных и текущего UI), новые автоматизации пишут в `runs`. Удалим в C5.

**Design decisions:**
- **Без ORM** — продолжаем raw SQL в `state.py` (стиль проекта).
- **`events` → `runs` 1:N**: одно событие может породить несколько runs, если на него подписаны несколько automations.
- **`runs` → `run_events` 1:N**: дерево вызовов агента и саб-агентов, как сейчас `task_events`.

**Что НЕ делать:**
- Не вводить YAML-конфиг автоматизаций — это отдельный change позже.
- Не миграцию `tasks` → `runs` — `tasks` живёт параллельно до C5.
- Не трогать `task_events` структурно (только `task_id` → `run_id` rename) — добавление полей и семантика — следующие блоки.

**Зависимости:** нет (фундамент).

**Начальные таски:**
1. SQL DDL для `events`, `runs`, `run_events` (новые миграции в `state.init_db`).
2. `models.py` — dataclasses `Event`, `Run`, обновить `RunEvent`.
3. `automations/registry.py` — `Automation` dataclass + список known automations (на старте только `dev_task` как заглушка, переписан в C5).
4. `session.py` — `compute_session_id` + тесты (детерминированность, нет коллизий для разных триггеров).
5. Обновить тесты `test_state.py`, `test_events.py`.

---

### C2 — `add-listener-runtime` · триггеры

**Цель:** ввести абстракцию `Listener` и долгоживущий runtime, который держит N listeners и пишет events в БД.

**Deliverables:**
- `Listener` base в `src/foundry/listeners/base.py` (`async def listen(emit: Callable[[Event], None])`).
- `GithubIssuesListener` — рефакторинг текущего `stages/fetch.py`, теперь работает в polling-loop'е, эмиттит events.
- `CronListener` — поддерживает несколько cron-rules, эмиттит events с `external_id = f"cron-{rule_id}-{tick_iso}"` или хешем «текущего часа», в зависимости от `dedup` стратегии (см. ниже).
- `DiscordListener` — stub с базовым контрактом (один TODO-class), реальная имплементация — отдельным change.
- CLI: `foundry serve` — поднимает все listeners в asyncio-tasks, пишет events в SQLite. `foundry run` (one-shot) остаётся как было — для CI и debug.

**Design decisions:**
- **Дедупликация event'ов** — на стороне БД через `UNIQUE(source, external_id)`. Listener эмиттит свободно, INSERT с `ON CONFLICT IGNORE` обеспечивает идемпотентность.
- **Cron-стратегия по умолчанию** — `external_id = f"cron-{rule_id}-{ISO}"` (новая сессия каждый tick). Для long-context cron-loop (типа «весь час одна сессия») — пользователь указывает `dedup: "hourly"` в конфиге, и `external_id` хешится с округлением.
- **`foundry serve` — однопроцессный asyncio-демон.** Без multi-process, без Redis. Если упадёт listener — лог + restart с backoff.

**Что НЕ делать:**
- Не делать webhook-приёмник (это отдельный listener позже).
- Не делать UI для управления listeners — пока конфиг в коде/env.
- Не реализовывать DiscordListener полностью — только signature.

**Зависимости:** C1.

**Начальные таски:**
1. `listeners/base.py`, `listeners/github_issues.py`, `listeners/cron.py`, `listeners/discord.py` (stub).
2. CLI-команда `foundry serve` в `cli.py`.
3. Перенести логику `stages/fetch.py` в listener; pipeline временно ходит к новому listener'у синхронно для legacy-режима.
4. Тесты на дедупликацию event'ов (re-emit того же `external_id` не создаёт дубликат).

---

### C3 — `add-mcp-subagent-server` · MCP вызова

**Цель:** локальный MCP-сервер, через который top-level агент сам вызывает sub-агентов и базовые «глобальные» tools.

**Deliverables:**
- `src/foundry/mcp/server.py` — stdio MCP-сервер на FastMCP.
- Tools:
  - `call_subagent(name: str, prompt: str, id: str) -> {response, cost_usd, duration_sec}` — рекурсивно вызывает агента (по имени из реестра саб-агентов), генерирует `sub_session_id = compute_session_id(id, sub_agent_type)`, пишет `agent_*` события в `run_events` с `parent_event_seq` для дерева. Возвращает только финальный response.
  - `mark_milestone(label: str)` — пишет `run_events` с `kind='mark'`.
  - `compact_context()` — заглушка, реализация после первой реальной потребности.
- Интеграция: `ClaudeCliAgent` запускается с `--mcp-config <path>` указывающим на foundry MCP server. Контекст текущего `run_id` пробрасывается через env.

**Design decisions:**
- **MCP-сервер один на всё**, tools регистрируются динамически per-run в зависимости от skills automation'а.
- **Контекст runа (`run_id`, `automation_id`, `parent_event_seq`)** — через env-переменные при запуске MCP-сервера, чтобы tools знали куда писать events.
- **Sub-agent backends — те же что top-level** (`claude_cli`, `codex_cli`, `opencode_cli`). `name` саб-агента в `call_subagent` — это id из реестра саб-агентов, не имя backend'а.

**Что НЕ делать:**
- Не делать remote MCP — только stdio.
- Не реализовывать `compact_context` глубоко — заглушка возвращает «not implemented yet».
- Не подключать MCP к существующему legacy `dev_task` — миграция в C5.

**Зависимости:** C1.

**Начальные таски:**
1. FastMCP сервер skeleton + регистрация одного tool (`mark_milestone`) для smoke.
2. `call_subagent` — реализация через `make_agent` + новый `sub_session_id`, запись в `run_events`.
3. Конфиг `claude --mcp-config` для подключения сервера.
4. Тесты: вызов `call_subagent` пишет правильное дерево событий, парный `parent_event_seq`.

---

### C4 — `add-automation-orchestrator` · общий flow

**Цель:** склеить C1+C2+C3 — демон ловит event, находит подписанные automations, запускает run с агентом + MCP-сервером + skills.

**Deliverables:**
- `src/foundry/orchestrator.py` — async loop, читает новые events из БД (или подписан на in-memory pubsub если listener в том же процессе), для каждого: находит automations с этим триггером, создаёт `Run` для каждого, запускает агента.
- Skills как MCP tools (тонкие обёртки над существующим кодом):
  - `open_worktree()` → `worktree.create_worktree`
  - `commit_and_push_pr(title, body)` → текущая логика `stages/pr.py`
  - `react_emoji(emoji)` → github reaction / discord reaction (через listener-callback)
  - `reply_discord(text)`, `open_github_issue(title, body)`, `read_diff(pr_id)` — по мере нужды
- Per-run MCP-config: orchestrator формирует `.mcp-config.json` с subset tools = automation.skills + всегда-доступные (`call_subagent`, `mark_milestone`).
- Интеграция с `foundry serve`: orchestrator поднимается рядом с listeners в том же процессе.

**Design decisions:**
- **In-process pubsub** между listener и orchestrator (asyncio Queue) — никакого Redis на старте. БД — backup для durability (event записан → orchestrator подберёт даже если упал).
- **Skill access — по declared list**. Если automation не имеет `create_pr` в `skills`, MCP tool недоступен. Это безопасность по умолчанию.
- **Failure handling** — terminal error агента → run.status=FAILED + failure_kind через verifier (см. C5 нюансы), нет автоматического retry. Retry — через UI кнопку «retry» (C6) которая создаёт новый run в той же session.

**Что НЕ делать:**
- Не делать прав на skills через UI — пока в коде.
- Не делать distributed orchestrator — однопроцессный.
- Не реализовывать все skills сразу — только нужные для миграции `dev_task` (C5).

**Зависимости:** C1, C2, C3.

**Начальные таски:**
1. `orchestrator.py` skeleton + интеграция с `foundry serve`.
2. `skills/worktree.py`, `skills/github.py` (open_issue, react), `skills/pr.py` (commit_and_push_pr).
3. Per-run MCP-config generation.
4. End-to-end тест: эмиттим event → orchestrator создаёт run → агент (stub backend) дёргает skill → результат в БД.

---

### C5 — `migrate-dev-task-to-automation` · legacy в новый мир

**Цель:** переписать `dev_task` как обычную automation на skills, удалить старый pipeline.

**Deliverables:**
- Automation `dev_task` в registry: `triggers=[github_issues]`, `agent={backend: claude_cli, model: ...}`, `prompt=prompts/dev_task.md`, `skills=[open_worktree, plan, implement, run_tests, create_pr, mark_milestone]`.
- Новый prompt `dev_task.md` — фиксирует контракт: «у тебя есть skills X, Y, Z; цель — реализовать issue, открыть PR; если verifier недоволен — итерируй; если требуется человек — вызови `wait_for_human(reason)`».
- Skills `plan` и `implement` — становятся опциональными MCP tools, агент сам решает звать ли их (для legacy сохранения структуры) или работать без них.
- Удаление: `pipeline.run_once`, `workflows.dev_task`, `workflows.pr_verify`, `stages/agent_plan.py`, `stages/agent_implement.py`, `stages/context.py`, `stages/verify.py`, `stages/pr.py` (логика переезжает в skills), `stages/fetch.py` (переехала в C2), `models.Stage` enum, `PRE_IMPLEMENT_STAGES` policy.
- `tasks` таблица — drop или mark `_legacy_tasks` (зависит от объёма данных у пользователя).

**Design decisions:**
- **Verifier тоже становится skill** (`run_tests`), агент сам решает когда вызывать. `failure_kind` парсится из stderr/exit_code или передаётся самим агентом через `mark_failed(kind, msg)` skill.
- **Retry-loop из текущего workflows.dev_task — больше нет.** Если хочется итерации plan→impl→verify — это делает сам агент в своём цикле reasoning, мы не управляем извне.
- **Параметры `max_implement_attempts` и `PRE_IMPLEMENT_STAGES` — удаляются.** Концепция исчезает: агент сам решает retry внутри своего бюджета токенов/времени.

**Что НЕ делать:**
- Не оставлять legacy pipeline в виде fallback — полная миграция или ничего.
- Не пытаться сохранить полное поведение workflows.dev_task — мы намеренно даём агенту больше свободы.

**Зависимости:** C1, C2, C3, C4.

**Начальные таски:**
1. `prompts/dev_task.md` — новый промпт.
2. Registry-запись `dev_task` automation.
3. Skill `run_tests`, skill `mark_failed`.
4. Удаление legacy кода + правка тестов.
5. Smoke-run на тестовом github-issue.

---

### C6 — `add-automations-ui-v2` · фронт

**Цель:** новый UI по утверждённым v2-мокапам ([`Foundry Automations.html`](../../design_handoff_foundry_observability/project/Foundry%20Automations.html)).

**Deliverables:**
- API endpoints в `src/api/`:
  - `GET /api/automations` — список с counts.
  - `GET /api/triggers` — список с health / last_seen.
  - `GET /api/automations/:id/runs` — runs одной automation.
  - `GET /api/runs?filter=running|waiting|failed` — inbox.
  - `GET /api/runs/:id` — run + дерево вызовов.
  - `GET /api/runs/:id/events` — SSE.
  - `POST /api/runs/:id/messages` — composer (continue / enqueue / reply).
  - `POST /api/runs/:id/stop` — остановка.
  - `POST /api/runs/:id/retry` — новый run в той же session.
- Frontend в `web/`:
  - 3 таба sidebar (Automations / Runs / Inbox).
  - Routines-style automations rows (тонкая иконка, имя, описание, Active/N running).
  - Triggers footer на табе Automations.
  - Run rows с моноcolor StatusGlyph + status word + attempt-badge.
  - Run Detail: header (status-pill + automation-pill + session_id + failure_kind pill + retry/open-source) + source-card + stats + SubagentMinimap + дерево + composer.
  - Дерево с раскрывающимися sub-agents и `mark` divider'ами.
  - Composer: один input, плейсхолдер по статусу.

**Design decisions:**
- **API alias-слой:** `/api/tasks/*` для legacy несколько недель → 404 после grace period. На запуске C6 — uniqueно `/api/runs/*`.
- **SSE polls БД** как сейчас (через `bus.subscribe`), без in-process pubsub — потому что orchestrator и uvicorn могут быть в разных процессах.
- **Light theme** добавляется в этом блоке (мокапы пока только dark, но claude.app-референс — light).

**Что НЕ делать:**
- Не делать настройки automations через UI (создание/редактирование) — отдельный change.
- Не делать UI для skills/MCP — это backend-конфиг.
- Не делать аутентификацию — single-user локально.

**Зависимости:** C1 (по данным), реально показывать после C4.

**Начальные таски:**
1. API: новые endpoints (read-only сначала, write — следом).
2. `web/src/` — рефакторинг под новые типы (Automation/Run/Event), удаление task-row.tsx.
3. Реализация sidebar с табами + AutomationsList + RunsList + InboxList.
4. Run Detail: header, source-card, дерево, SubagentMinimap, composer (read-only mode).
5. Composer: write endpoints + интеграция.

---

## Открытые вопросы (решить когда дойдём)

- **Q1. Сливать ли C2+C3 в один change?** Оба нужны для C4, по отдельности — мёртвые куски кода. Дефолт: оставить отдельно (легче ревьюить). Решить перед стартом C2.
- **Q2. `tasks` таблица — drop или legacy archive?** Зависит от объёма данных и желания сохранить старые runs в UI. Решить в C5.
- **Q3. Регистр automations: код vs YAML.** Дефолт: код на старте, YAML — отдельным change позже когда станет очевидно что нужен. Решить в C1.
- **Q4. `session_id` алгоритм.** Кандидаты:
  - `sha1(external_id + "|" + automation_id + "|" + agent_type)[:12]` — компактно, нечитаемо в логе.
  - `f"{external_id}-{automation_id}-{agent_type}"` — читаемо, длинно.
  - `uuid5(NAMESPACE_FOUNDRY, external_id + automation_id + agent_type)` — стандартизованно, длинно.
  Решить в C1.
- **Q5. Дедупликация cron-event'ов** — по умолчанию `external_id = cron-{rule}-{tick_iso}` (новая сессия каждый tick), либо хеш с округлением (по часу/дню). Решить в C2.
- **Q6. Failure detection без явного `mark_failed`** — если агент завершил без явного сигнала, как определить что upstream сломался? Через verifier-skill exit_code? Через regex на «error» в финальном response? Дефолт: агент обязан вызвать `mark_done` или `mark_failed(kind, msg)` skill, иначе run.status=`UNCLEAR`. Решить в C5.

## Прогресс

- [x] C1 — add-event-and-automation-model
- [x] C2 — add-listener-runtime
- [x] C3 — add-mcp-subagent-server
- [x] C4 — add-automation-orchestrator
- [ ] C5 — migrate-dev-task-to-automation
- [ ] C6 — add-automations-ui-v2
