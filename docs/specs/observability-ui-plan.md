# Observability & Live UI — план реализации

> Инженерный roadmap к макетам из [design_handoff_foundry_observability/](../../design_handoff_foundry_observability/) и постановке в [observability-ui.md](observability-ui.md). Делим работу на 6 PR'ов, каждый самодостаточен, UI зажигается на PR5.

## Архитектурные решения (зафиксированы)

1. **Одна append-only таблица `task_events`** — источник истины для всего, что видит UI. Не `stage_runs` + `events` (преждевременная нормализация), не раздувание `logs_json` (нельзя стримить/пагинировать).
2. **`logs_json` в `tasks` оставляем как есть** — сырой дневник, не мигрируем.
3. **Синхронный `record_event()`** — пайплайн не требует event loop. FastAPI-слой добавляет pubsub сверху опционально.
4. **Atomic `seq` per task** — в одной транзакции `MAX(seq)+1` + `INSERT`.
5. **SSE (не WebSocket)** — однонаправленный live-журнал, `Last-Event-ID` для реконнекта, replay из SQLite.
6. **Streaming JSONL через `subprocess.Popen`** — `for line in stdout`, никакого asyncio в агентском слое. Контракт `CodingAgent.apply()` не трогаем.
7. **Alias стадий только в `projections.py`** — в БД и pipeline внутренние имена (`plan`, `implement`, `verify`). Фронту отдаём `agent_plan` / `agent_implement` из мэппера.
8. **Ask-composer = UI-заглушка в v1** — требует агент-resume, отдельная задача.
9. **`POST /api/run` выносим из read-only observability** — отдельный PR после обзора.
10. **Langfuse остаётся внешней глубокой трассировкой** — Foundry UI показывает операционную картину.

---

## Схема `task_events`

```sql
CREATE TABLE task_events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    INTEGER NOT NULL,
  seq        INTEGER NOT NULL,           -- монотонный per-task, для SSE Last-Event-ID
  stage      TEXT    NOT NULL,           -- внутренние имена FSM: plan/implement/verify/...
  kind       TEXT    NOT NULL,
  ts_ms      INTEGER NOT NULL,
  payload    TEXT    NOT NULL,           -- JSON
  UNIQUE (task_id, seq)
);
CREATE INDEX idx_task_events_task_seq ON task_events(task_id, seq);
```

### Контракт `kind` + payload

| kind              | когда                        | payload                                                                 |
|-------------------|------------------------------|-------------------------------------------------------------------------|
| `stage_started`   | вход в стадию                | `{agent?: {name,model,provider}, input?: IOData}`                       |
| `stage_finished`  | успешный выход               | `{duration_ms, cost_usd?, tokens_in?, tokens_out?, output?: IOData}`    |
| `stage_failed`    | исключение                   | `{duration_ms, error, traceback}`                                       |
| `agent_tool`      | `tool_use` из stream-json    | `{tool, detail?, args?}`                                                |
| `agent_thinking`  | блок размышлений             | `{text}`                                                                |
| `agent_text`      | текст ответа агента          | `{text}`                                                                |
| `agent_result`    | финал агента                 | `{summary}`                                                             |

`IOData` — union из handoff: `kv | files | text | error | pending`.

### Truncation

- **Длинные поля** (`text`, `stdout`, `stderr`, `input`, `output` внутри payload): при > 64KB →
  `{text: "...<head>...", truncated: true, original_size: N}`.
- **Короткие критичные** (`tool`, `detail`, `summary`, `error`, `model`): всегда verbatim.
- Truncation — per field, не per payload.

---

## Модули

```
src/foundry/events.py           # record_event() sync, read_events(after_seq), truncation
src/foundry/agents/streaming.py # iter_cli_jsonl() — Popen + построчный for line in stdout
src/api/projections.py          # Task + events → UiTask (здесь STAGE_ALIAS)
src/api/sse.py                  # EventSource endpoint (PR4)
src/api/bus.py                  # in-process pubsub (PR4, поверх record_event)
web/                            # Vite + React + TS (PR5+)
```

---

## PR1 — `task_events` + writer

**Цель:** append-only storage и чтение, без интеграции в pipeline.

**Делаем:**
- Миграция в `state.init_db`: создание `task_events` и индекса.
- `src/foundry/events.py`:
  - `record_event(db_path, task_id, stage, kind, payload) -> int` (возвращает `seq`).
  - Одна транзакция: `SELECT COALESCE(MAX(seq),0)+1` + `INSERT`.
  - `read_events(db_path, task_id, after_seq=None, limit=None) -> list[Event]`.
  - `_truncate_payload(payload)` — helper с правилами выше.
- `Event` — dataclass в `models.py` (`id, task_id, seq, stage, kind, ts_ms, payload`).

**Тесты** (`tests/test_events.py`, AAA-style):
- atomic seq под concurrent записями (threaded insert → 1..N без дырок/дублей).
- `read_events` с `after_seq` отдаёт хвост в правильном порядке.
- truncation: длинный `text` → `truncated: true`; короткий `summary` не режется.
- невалидный `kind` / неизвестная стадия — behavior выбрать (разрешаем строки, валидация на писателе verbose, но не падаем).

**Не делаем:** ring-buffer, pubsub, интеграцию с pipeline, API.

---

## PR2 — Stage lifecycle events в pipeline

**Цель:** каждая стадия эмитит `stage_started/finished/failed`. Stub-agent уже даёт UI «живую» картину без Claude CLI.

**Делаем:**
- В `src/foundry/events.py` — context manager:
  ```python
  @contextmanager
  def stage_span(db_path, task_id, stage, *, input=None, agent=None):
      record_event(... kind="stage_started" ...)
      t0 = time.monotonic()
      try:
          yield lambda output, cost=None, tokens_in=None, tokens_out=None: ...
          record_event(... kind="stage_finished" ...)
      except Exception as e:
          record_event(... kind="stage_failed" ...)
          raise
  ```
- Обернуть в `pipeline._process_task` стадии `context`, `plan`, `implement`, `verify`, `pr`. `fetch` — опционально (стадия батчевая, не per-task).
- `StubAgent` в обоих стадиях эмитит 2–3 синтетических события (`agent_thinking`, `agent_tool`, `agent_result`) через `record_event`.
- Сигнатуры `*_stage.run(...)` **не меняем** — они получают `db_path` через `settings`.

**Тесты:**
- `test_pipeline.py`: happy path оставляем как есть; добавляем проверку, что после прохода в `task_events` лежит последовательность `stage_started → agent_* → stage_finished` для каждой стадии.
- failure path: `stage_failed` с traceback, `PRE_IMPLEMENT_STAGES` re-queue всё ещё работает.

**Не делаем:** реальный stream от Claude CLI — это PR3.

---

## PR3 — Streaming JSONL для агентов

**Цель:** `tool_use` события прилетают в UI по ходу стадии, не после.

**Делаем:**
- `src/foundry/agents/streaming.py`:
  - `iter_cli_jsonl(cmd, *, cwd, env) -> Iterator[dict]` на `subprocess.Popen` + `for line in proc.stdout`.
  - Возвращает dict'ы; обработка ошибок парсинга — пропускать с `log.warning`, не падать.
- `ClaudeCliAgent.apply()`:
  - Переключить с `run_cli_jsonl` на `iter_cli_jsonl`.
  - На каждой линии: если `type=tool_use` → `record_event(kind="agent_tool", ...)`; если `assistant` с text block → `agent_text`; если thinking → `agent_thinking`.
  - Финальный `result` блок → `agent_result` + накопленный usage возвращается в `AgentResult` как раньше.
- Нормализатор `_normalize_tool_event(raw) -> {tool, detail?, args?}` — один на все агенты (`claude_cli`, `codex_cli`, `opencode_cli`).
- `codex_cli` и `opencode_cli` — в этом же PR по аналогии, если схемы близкие. Если сильно разные — отдельный PR3.5.

**Контракт НЕ ломаем:** `apply()` по-прежнему возвращает `AgentResult`. Просто по пути эмитит события.

**Тесты:**
- Моки `Popen` с фиктивным JSONL — проверяем, что `agent_tool` события появляются в `task_events` до `stage_finished`.
- Парсинг tool_use с разными инструментами (Read/Edit/Bash/Grep) → правильный `detail`.

---

## PR4 — FastAPI: projections + SSE

**Цель:** UI-friendly API поверх `tasks` + `task_events`. Read-only.

**Делаем:**
- `src/api/projections.py`:
  - `STAGE_ALIAS = {"plan": "agent_plan", "implement": "agent_implement"}` (остальные 1:1).
  - `project_task(task, events) -> UiTask` — складывает `stages[stage] = {status, duration, cost, tokens, agent, input, output, error}` из событий. Agregates (`total_cost_usd`, `tokens_total`, `duration_sec`) — суммой по `stage_finished`.
  - Типы `UiTask`, `UiStage`, `UiEvent` — Pydantic.
- `src/api/bus.py`:
  - `EventBus` — `asyncio.Queue` на подписчика, `publish(event)` non-blocking.
  - `subscribe(task_id, after_seq) -> AsyncIterator[Event]`: сначала `read_events(db, task_id, after_seq)` (catch-up из SQLite), затем live из queue.
  - Подписка на `record_event` — через тонкий callback, который `bus` регистрирует в `events.py` (список callbacks, вызывается после commit).
- `src/api/sse.py`:
  - `GET /api/tasks/{id}/events` — SSE endpoint, `Last-Event-ID` → `after_seq`.
  - Формат: `id: {seq}\nevent: {kind}\ndata: {json}\n\n`.
- Эндпоинты:
  - `GET /api/tasks` — `UiTask[]`, сводно (без `events`).
  - `GET /api/tasks/{id}` — полный `UiTask` с последними N событиями.
  - `GET /api/repos` — `[{repo, counts: {RUNNING, DONE, FAILED, PENDING}}]`.

**Тесты:**
- `test_api.py`: проекция складывает корректный `UiTask` из фикстуры событий.
- SSE: коннект без `Last-Event-ID` → replay всё; с `Last-Event-ID: 5` → только события с `seq > 5`.
- Live: `record_event` во время открытого SSE → подписчик получает.

**Не делаем:** `POST /api/run`, `/api/tasks/{id}/ask`.

---

## PR5 — `web/` scaffold + таблица задач

**Цель:** статический табличный layout из handoff на реальных данных.

**Делаем:**
- `web/`: Vite + React + TS + `lucide-react` + `@tanstack/react-query`.
- Перенос CSS tokens из `design_handoff_foundry_observability/styles.css` 1:1.
- Компоненты: `Sidebar`, `Topbar`, `FilterBar`, `TableHeader`, `TaskRow` (только свёрнутая), `StatusChip`, `StageStepper` (size="sm"), `AgentBadge`.
- `src/api.ts` — клиент на fetch, типы из handoff README.
- `GET /api/tasks` + `GET /api/repos` через `useQuery`, рефетч каждые 3 сек.
- Без роутинга (одна страница), без auth, без dark/light toggle (dark по умолчанию — как в handoff).

**Не делаем:** expanded panel, SSE, композер.

---

## PR6 — Expanded panel + live stream

**Цель:** раскрытая задача со stepper, stage detail, живой EventStream.

**Делаем:**
- `TaskDetails`, `StageDetailPanel`, `StageIO`, `EventStream` (style="telegram" по умолчанию).
- `useTaskStream(id)` — хук на `EventSource`, мержит в store, сохраняет `lastEventId`.
- Кликабельный `StageStepper size="lg"` → `selectedStage`.
- `AskAgentComposer` — UI-only, кнопка «Задать вопрос» дисейблнута с тултипом «скоро».

**Не делаем:** `POST /ask`.

---

## Дальше (не в этом roadmap)

- `POST /api/run` и `POST /api/tasks/{id}/retry` — management endpoints, отдельным PR.
- Ask-composer с реальным agent-resume.
- Auth (если UI выйдет за пределы localhost).
- Карточный/компактный layout из прототипа `Foundry Observability.html`.
- Материализованная проекция `stage_runs`, если `project_task` станет bottleneck'ом (маловероятно на SQLite).

---

## Принципы на которые мы не поведёмся

- **Не делаем mini-Langfuse.** Langfuse — внешний, глубокий; Foundry UI — операционный.
- **Не вводим ORM.** Остаёмся на raw SQL через `state.py` / `events.py`.
- **Не тянем asyncio в агентский слой.** Popen + for loop достаточно.
- **Не переименовываем FSM стадии.** Alias в проекции — всё.
- **Не блокируем CLI на FastAPI.** `record_event` работает без event loop; pubsub — опциональная надстройка.
