# Foundry simplification — план на 2026-05

Цель: убрать legacy от старой staged-модели и сжать конфигурацию `Automation`,
не вводя новых абстракций. Размер кода падает, число центральных понятий
остаётся прежним (3: Trigger/Event, Automation, Run).

## Принципы

- Никаких новых протоколов / strategy-классов. У нас 3 automations.
- Никаких миграций БД на этом проходе. Колонку `run_events.stage` не трогаем
  — она несёт живую семантику ("run_lifecycle", "subagent:echo", и т.д.).
- Каждая фаза = отдельный коммит, зелёный `pytest`.
- Перед фазой 1 — характеризационные тесты (фаза 0). После каждой фазы они
  должны оставаться зелёными.
- На каждой фазе агент-исполнитель делает работу, code-reviewer ревьюит,
  только потом коммит.

## Acceptance criteria для всего рефакторинга

- `pytest` зелёный.
- 3 характеризационных e2e теста (по одному на `dev_task` / `tg_chat` /
  `pr_review`) проходят на StubAgent: финальный `Run.status`, набор kinds в
  `run_events`, факт вызова правильного skill.
- `AgentStage` нигде не упоминается (`grep -r AgentStage` пусто).
- В `Automation` одно поле `workspace` вместо `cwd / git_worktree / pr_worktree`.
- `orchestrator.py` ≤ 200 строк, новый `runner.py` содержит execute-логику.
- CLAUDE.md и `docs/architecture/*` обновлены.

---

## Фаза 0 — характеризационные тесты (safety net)

**Что:** написать (или дополнить существующие) e2e тесты на 3 автоматизации
со `StubAgent`, чтобы дальнейшие фазы не сломали поведение незаметно.

**Шаги:**
- [ ] Аудит существующих `tests/test_orchestrator_integration.py` —
      покрывает ли все 3 автоматизации end-to-end.
- [ ] Добавить недостающие сценарии:
  - [ ] `dev_task`: `github.issue_opened` → run DONE → `commit_and_push_pr`
        вызван 1 раз с правильными аргументами, worktree создался под
        `WORKTREE_ROOT/task-{run_id}`.
  - [ ] `tg_chat`: 2 события с одним `chat_id` → один `session_id` на оба
        run-а; `cwd` совпадает с `Path("~/w/datura/lium/main").expanduser()`;
        `telegram_reply` вызван.
  - [ ] `pr_review`: 2 события на один PR → один `session_id`,
        `pr_worktree` материализуется.
- [ ] Snapshot набора `run_events.kind` для каждого happy-path сценария
      (только kinds + порядок, без timestamps).
- [ ] Все стабовые двойники (`StubAgent`, fake `gh`/`git` через
      monkeypatch на `shell.run`) — в одном `tests/conftest.py` или
      `tests/_doubles.py`.

**Проверка:** `uv run pytest -k characterization` зелёный, тесты
повторяемы (запустить 5 раз — стабильно).

**Коммит:** `test: характеризационные e2e на 3 автоматизации (safety net)`

---

## Фаза 1 — убить `AgentStage`

**Что:** удалить enum и его проводку. Поле `stage` в `record_event` /
`run_events` остаётся (живая семантика namespace).

**Шаги:**
- [ ] `src/foundry/agents/base.py` — удалить `AgentStage`, поле `stage`
      из `AgentTask` и `AgentResult`.
- [ ] `src/foundry/agents/config.py` — `DEFAULT_MAX_TURNS: int = 50`
      (одно число вместо dict). `AgentSettings.from_env()` без параметра.
- [ ] `src/foundry/agents/factory.py` — `make_agent(settings)` без stage.
- [ ] `src/foundry/agents/{stub,claude_cli,codex_cli,opencode_cli}.py` —
      убрать `self.stage = settings.stage`.
- [ ] `src/foundry/agents/__init__.py` — убрать экспорт `AgentStage`.
- [ ] `src/foundry/orchestrator.py:164` и `src/foundry/mcp/runner.py:59` —
      убрать `stage=AgentStage.IMPLEMENT` из `AgentTask(...)`. В вызове
      `stage_span(...)` заменить `AgentStage.IMPLEMENT` строкой
      `"implement"` (или просто `"run"` — выбираем при работе).
- [ ] Тесты:
  - [ ] `tests/test_agents_factory.py` — переписать под новый API.
  - [ ] `tests/test_agents_config.py` — без stage.
  - [ ] `tests/test_agents_{claude,codex,opencode}_cli.py` — убрать stage
        из `_settings`.
  - [ ] `tests/test_orchestrator*.py` — убрать `AgentStage` из стабов.
- [ ] `grep -r "AgentStage" src tests` пусто.
- [ ] Файлы `src/foundry/agents/prompts/{plan,implement,verify}.md` —
      уже удалены (видно в `git status`). Убедиться что нет загрузчиков.

**Проверка:**
- `uv run pytest` зелёный.
- Характеризационные тесты из фазы 0 — без изменений.
- Запустить code-reviewer subagent на diff.

**Коммит:** `refactor: удалить AgentStage (мёртвый артефакт staged-модели)`

---

## Фаза 2 — workspace как один дискриминатор

**Что:** свести `cwd / git_worktree / pr_worktree` в одно поле
`Automation.workspace`.

**Шаги:**
- [ ] Решить форму поля. Кандидат:
  ```python
  Workspace = (
      Literal["ephemeral"]
      | tuple[Literal["git_worktree"], None]
      | tuple[Literal["pr_worktree"], None]
      | tuple[Literal["fixed"], Path]
  )
  ```
  или проще — `Literal[...] + cwd: Path | None` остаётся, но один literal
  вместо двух булевых. Финал согласовать в первом коммите фазы.
- [ ] `src/foundry/automations/registry.py` — обновить `Automation` и
      три записи (`DEV_TASK / TG_CHAT / PR_REVIEW`).
- [ ] `src/foundry/orchestrator.py` (или `runner.py` после фазы 3) —
      заменить лестницу `if a.git_worktree: ... elif a.pr_worktree: ...`
      одним `match`.
- [ ] `tests/test_automations_registry.py` и тесты оркестратора — обновить.
- [ ] Характеризационные тесты — без изменений.

**Проверка:**
- `uv run pytest` зелёный.
- Один `match` в коде; нет одновременной проверки `git_worktree` и
  `pr_worktree`.
- code-reviewer subagent.

**Коммит:** `refactor: Automation.workspace вместо cwd/git_worktree/pr_worktree`

---

## Фаза 3 — выделить `runner.py`

**Что:** распилить `orchestrator.py` (436 строк) на цикл и исполнение run-а.

**Шаги:**
- [ ] Создать `src/foundry/runner.py`. Туда переехать:
  - подготовка workspace (worktree / pr_worktree / fixed / ephemeral),
  - сборка MCP config,
  - спавн агента, парс STATUS,
  - запись `run_events` (старт/финиш/фейл).
  - публичный API: `execute_run(run, automation, event, settings) -> RunStatus`.
- [ ] `orchestrator.py` оставить только: recover orphans, drain loop,
      `claim_pending_run`, вызов `runner.execute_run`. Цель ≤ 200 строк.
- [ ] Перенести соответствующие тесты:
  - `tests/test_runner.py` — юнит-тесты на `execute_run` без асинхронного
    цикла.
  - `tests/test_orchestrator.py` — оставить только цикл/claim/recover.
- [ ] Характеризационные тесты — без изменений.

**Проверка:**
- `uv run pytest` зелёный.
- `wc -l src/foundry/orchestrator.py` ≤ 200.
- code-reviewer subagent.

**Коммит:** `refactor: вынести execute_run в foundry/runner.py`

---

## Фаза 4 — документация

**Что:** обновить CLAUDE.md и `docs/architecture/*` под новый код.

**Шаги:**
- [ ] `CLAUDE.md`:
  - убрать упоминания `AgentStage` / `AgentStage.IMPLEMENT`,
  - описать новый `workspace`-дискриминатор,
  - описать `runner.py` отдельно от orchestrator.
- [ ] `docs/architecture/automations-roadmap.md` и
      `docs/architecture/agent-protocol.md` — пройтись по тексту.
- [ ] Удалить `docs/architecture/draft.md` если он стал неактуален
      (предварительно прочитать).

**Проверка:** ручное чтение, никаких тестов.

**Коммит:** `docs: обновить архитектурные заметки под упрощение`

---

## Протокол исполнения (как делаем фазы)

Для каждой фазы:

1. Я (главный агент) пишу подробный prompt для исполнителя — что именно
   делать, какие файлы, какие тесты.
2. Запускаю **исполнителя** (subagent_type=`general-purpose` или прямые
   правки в основной сессии — выбираем по объёму).
3. После работы — запускаю **code-reviewer subagent** на diff.
4. Если code-reviewer нашёл блокеры — фиксим, идём на круг.
5. `uv run pytest` локально.
6. Коммит одной строкой по нашему стилю.
7. Перехожу к следующей фазе.

Между фазами я остаюсь на связи: показываю diff и итоги перед коммитом.

## Открытые вопросы

- В фазе 2 — финальная форма `Workspace`. Решаем в первом коммите фазы.
- В фазе 1 — оставить ли `stage_span(..., "implement")` константой или
  переименовать аргумент в `record_event` на `section`. Голосую за
  «оставить параметр `stage`, передавать строку» — минимум изменений
  и call-site остаются понятными.
