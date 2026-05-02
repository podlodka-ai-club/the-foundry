# Foundry MCP-сервер

Локальный stdio MCP-сервер на FastMCP, через который top-level агент сам зовёт sub-агентов и базовые «глобальные» tools. Подключается к `claude` CLI через `--mcp-config <path>` (см. [`examples/foundry-mcp-config.json`](../../examples/foundry-mcp-config.json)).

Запуск: `uv run python -m foundry.mcp.server`.

## Tools

- `mark_milestone(label)` — пишет событие `kind='mark'` со `stage='milestone'` в `run_events`. Используется агентом, чтобы помечать узловые точки в дереве вызовов; UI рендерит как divider.
- `compact_context()` — заглушка, возвращает `{"ok": false, "error": "not implemented yet"}`. Реальная имплементация после первой реальной потребности.
- `call_subagent(name, prompt, id)` — рекурсивно вызывает зарегистрированного sub-агента (`name` ищется в `src/foundry/subagents/registry.py`). Пишет парные `agent_call_started` / `agent_call_finished` (или `agent_call_failed`) под `stage='subagent:<name>'`. Все внутренние events саб-агента нестятся под `started_seq` через `parent_event_seq` — UI разворачивает дерево по этой связи. Возвращает `{ok, response, cost_usd, duration_sec, sub_session_id}`.

## Env contract

Сервер читает env на каждом вызове tool'а (не при импорте):

- `FOUNDRY_DB_PATH` — путь к SQLite с таблицами `runs` / `run_events` (обязательно).
- `FOUNDRY_RUN_ID` — id текущего run'а, под который пишутся events (обязательно).
- `FOUNDRY_PARENT_EVENT_SEQ` — опциональный родительский seq в дереве событий. Если задан — все верхнеуровневые events tool'ов (включая framing `agent_call_started`) нестятся под него.
- `FOUNDRY_WORKTREE` — рабочая директория саб-агента (только для `call_subagent`); по умолчанию `os.getcwd()`.

## `sub_session_id`

`sub_session_id = compute_session_id(caller_id, sub.name, sub.backend)` — детерминированная функция от тройки. Сигнатура `compute_session_id(external_id, automation_id, agent_type)` зафиксирована в C1, здесь применяется role-aliasing: `caller_id → external_id`, имя саб-агента → `automation_id`, бэкенд → `agent_type`. Один и тот же caller, зовущий тот же саб-агент → та же session, так что CLI может `--resume`.

## Что отложено

- **C4** — per-run генерация `.mcp-config.json` оркестратором (subset tools = `automation.skills` + always-on `call_subagent` / `mark_milestone`); полный lifecycle `runs` (`finish_run` / `fail_run`).
- **C5** — реальные prompt-driven sub-агенты (сейчас в реестре только stub `echo`); миграция legacy `dev_task` на skills через MCP.
