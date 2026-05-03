# Telegram listener — план

Цель: «живой» демо для UI. Бот `@proactive_helper_bot` слушает приватные сообщения,
оркестратор крутит автоматизацию `tg_chat`, агент отвечает обратно в тот же чат.
Каждое сообщение = новый `Run`, но контекст сквозной: `session_id = "tg-{chat_id}"`,
поэтому `claude_cli --resume` подтягивает прошлый разговор.

## Объём (что делаем)

- [ ] **Config** — добавить `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS` (CSV chat_id), `TELEGRAM_POLL_SEC` в [config.py](src/foundry/config.py) и `.env.example`.
- [ ] **Listener** — `src/foundry/listeners/telegram.py`:
  - long-polling `getUpdates?offset=...&timeout=25`
  - фильтр: только `update.message`, только `chat.type == "private"`, `from.id in allowed`
  - emit `Event(source="telegram", external_id=f"tg:{update_id}", kind="message", payload={chat_id, user_id, username, text, message_id})`
  - offset восстанавливается при старте через `MAX(id) WHERE source='telegram'` (через новый хелпер `state.last_external_id(source)`) → `getUpdates(offset=last+1)`
- [ ] **Skill `telegram_reply`** — `src/foundry/skills/telegram_reply.py`:
  - `telegram_reply(text: str) -> {"ok": bool}`
  - читает `FOUNDRY_TG_CHAT_ID` из env (оркестратор прокидывает из `event.payload`)
  - вызывает Bot API `sendMessage`
- [ ] **Automation `tg_chat`** — в [registry.py](src/foundry/automations/registry.py):
  - `triggers=("telegram",)`, `agent={"backend": "claude_cli", "model": "sonnet"}`
  - `skills=("telegram_reply", "mark_done", "mark_failed")`
  - `prompt_path="prompts/tg_chat.md"`
- [ ] **Prompt** — `src/foundry/automations/prompts/tg_chat.md`: «ты ассистент, отвечай через `telegram_reply`, в конце вызови `mark_done`».
- [ ] **Session pinning** — точечная правка в [orchestrator.py](src/foundry/orchestrator.py) `_create_and_dispatch`: для `event.source == "telegram"` использовать `session_id = f"tg-{chat_id}"` вместо `compute_session_id(...)`. Так в одном чате — одна сквозная беседа.
- [ ] **Env-проброс в MCP-subprocess** — добавить `FOUNDRY_TG_CHAT_ID` рядом с `FOUNDRY_DB_PATH`/`FOUNDRY_RUN_ID` в [orchestrator.py](src/foundry/orchestrator.py) (для telegram-events).
- [ ] **Factory** — зарегистрировать `telegram` в [_factory.py](src/foundry/listeners/_factory.py).
- [ ] **Skill registry** — добавить `telegram_reply` в [skills/__init__.py](src/foundry/skills/__init__.py).
- [ ] **Тесты** — `tests/test_telegram_listener.py`: dedup, allowlist, offset-restore (через mock `httpx`).

## Что НЕ делаем (намеренно)

- Группы/каналы — только приватные чаты.
- `@mention` детектор — отвечаем на каждое сообщение от allowlisted user.
- Webhooks — только long-polling, никакого ngrok.
- Фото/файлы/inline — только `text`.
- Worktree-флоу — `tg_chat` не делает PR; это чистый чат-бот.
- Streaming-ответ в TG (по 1 сообщению на ход) — отвечаем одним `sendMessage` после того как агент завершил мысль.
- Persistence offset в отдельной таблице — переиспользуем `events.id` через `last_external_id(source)`.

## Как тестировать

1. `cp .env.example .env` → вписать `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS=1405827137`.
2. `LISTENERS_ENABLED=telegram uv run foundry serve` — поднимает листенер + оркестратор без GitHub.
3. Параллельно — `uvicorn` + `vite` уже подняты (UI на :5173).
4. Пишем боту → видим в UI: новый event в Inbox → новый run в `tg_chat` → event tree с вызовом `telegram_reply` → `mark_done`. Бот пишет ответ в TG.
5. Второе сообщение в тот же чат → новый run, но `session_id` тот же → `claude_cli` помнит первое.

## Открытые вопросы

- Что делать, если у `claude_cli` нет валидного предыдущего session_id (первое сообщение)? — `_find_resume_session_id` уже умеет возвращать `None`; backend стартует свежую сессию.
- Allowlist пустой — пускать всех? — **нет**, считать misconfig и логировать warning, не emit'ить event.
