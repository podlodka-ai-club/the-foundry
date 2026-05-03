# Foundry — расширение

Как добавить **новый листенер** и **новую автоматизацию**. Подразумевается,
что ты уже прочитал [overview.md](overview.md) — там схемы потока данных и
ключевые инварианты.

---

## 1. Новый listener

Listener — это long-running asyncio-таск, который наблюдает за внешним
источником и вызывает `emit(...)`. Дальше работу делает `dispatch_event`:
вставляет `events`-row и по одной `PENDING`-run на каждую подписанную
автоматизацию (одной транзакцией). Дедупликация — на уровне БД через
`UNIQUE(trigger_id, external_id)`.

### Шаги

1. **Зарегистрировать `trigger_id`** в
   [`src/foundry/triggers.py`](../../src/foundry/triggers.py).
   Имя: `<namespace>.<event>` (точки, не двоеточия). Положить в `ALL`,
   чтобы `validate_registry` принял его как известный.

   ```python
   SLACK_MENTION = "slack.mention"

   ALL: frozenset[str] = frozenset({
       ...,
       SLACK_MENTION,
   })
   ```

2. **Написать listener-класс** в
   [`src/foundry/listeners/`](../../src/foundry/listeners/). Шаблон:

   ```python
   # src/foundry/listeners/slack.py
   from __future__ import annotations

   import asyncio
   import structlog

   from .. import triggers
   from .base import EmitFn

   log = structlog.get_logger(__name__)


   class SlackListener:
       id = "slack"          # стабильный id (settings.listeners_enabled, supervision)
       source = "slack"      # coarse grouping для last_external_id

       def __init__(self, *, token: str, poll_sec: int = 30) -> None:
           self.token = token
           self.poll_sec = poll_sec

       async def tick_once(self, emit: EmitFn) -> None:
           """Один проход: pull-источник → emit. Public для тестов."""
           mentions = await asyncio.to_thread(self._fetch_mentions)
           for m in mentions:
               await emit(
                   trigger_id=triggers.SLACK_MENTION,
                   dedupe_key=f"slack#{m['ts']}:{m['channel']}",
                   payload={
                       "channel": m["channel"],
                       "user": m["user"],
                       "text": m["text"],
                       "ts": m["ts"],
                       "short_name": f"@{m['user']}",
                   },
               )

       async def listen(self, emit: EmitFn) -> None:
           while True:
               try:
                   await self.tick_once(emit)
               except asyncio.CancelledError:
                   raise
               except Exception:
                   log.exception("listener.tick.error", listener=self.id)
               await asyncio.sleep(self.poll_sec)

       def _fetch_mentions(self) -> list[dict]:
           ...   # sync I/O, ушёл бы в asyncio.to_thread
   ```

   Контракт смотри в [`listeners/base.py`](../../src/foundry/listeners/base.py)
   (`Listener` и `EmitFn` — оба `Protocol`). Поля `id` / `source` —
   обычные class-атрибуты, не свойства.

3. **`dedupe_key`** — стабильный ключ внешнего объекта (у GitHub это
   `repo#123`, у Telegram `tg:<chat>:<msg_id>`, у cron — id «удара»). При
   повторном emit с тем же `dedupe_key` `dispatch_event` ничего не делает.
   Если ключ переменится — будет дубль run-а.

4. **Подключить листенер** в
   [`listeners/_factory.py`](../../src/foundry/listeners/_factory.py).
   Если он опциональный (нужен токен/чат) — поставь guard как у
   `TelegramListener`:

   ```python
   if settings.slack_token:
       all_listeners.append(SlackListener(token=settings.slack_token))
   ```

5. **Конфиг** — добавить поля в
   [`foundry.config.Settings`](../../src/foundry/config.py) (env-vars
   читаются через `python-dotenv` лениво) и пример в
   [`.env.example`](../../.env.example).

6. **Тесты** в
   [`tests/test_listener_slack.py`](../../tests/) — AAA-стиль, обычно
   моки на `_fetch_mentions` или на `shell.run`. Не запускать реальные
   network-вызовы. Пример в
   [`tests/test_listener_github_issues.py`](../../tests/test_listener_github_issues.py).

7. (Опционально) **Описание для UI**: префикс `slack.` появится в
   `/api/triggers` автоматически, если листенер успел emit-нуть хоть
   один event. Документация автоматизаций может ссылаться на новую
   константу прямо.

### Что НЕ должен делать listener

- Не лезть в `state.py` напрямую (никакого `state.insert_event(...)`).
  Только через `EmitFn`.
- Не знать про автоматизации. `dispatch_event` сам найдёт подписчиков
  через `automations_for_trigger(trigger_id)`.
- Не парсить статусы run-ов / не писать в `run_events`. Это работа
  оркестратора и агента.
- Не держать собственный курсор. Если нужно «откуда продолжить» — есть
  `state.last_external_id(source)`.

---

## 2. Новая automation

Automation — декларативная запись в
[`src/foundry/automations/registry.py`](../../src/foundry/automations/registry.py),
которая говорит:

- какие `trigger_id` подписаны (один или несколько),
- какой агент-бэкенд / модель использовать,
- где взять промпт,
- как готовить рабочий каталог (`workspace`),
- (опционально) как склеивать события в одну агентную сессию
  (`session_key`).

Никакого отдельного класса/протокола — просто `Automation(...)`-инстанс
в `AUTOMATIONS`-списке. На старте `serve` `validate_registry` проверит,
что все упомянутые триггеры известны.

### Шаги

1. **Промпт** — `.md`-файл рядом с уже существующими в
   [`src/foundry/automations/prompts/`](../../src/foundry/automations/prompts/).
   Стиль: что агент должен сделать, какие FOUNDRY_*-env vars доступны,
   какой `STATUS:` маркер от него ожидается. Подсмотри в
   [`dev_task.md`](../../src/foundry/automations/prompts/dev_task.md)
   или [`pr_review.md`](../../src/foundry/automations/prompts/pr_review.md).

2. **Запись в реестре**:

   ```python
   from foundry import triggers
   from foundry.automations.registry import Automation

   SLACK_TRIAGE = Automation(
       id="slack_triage",
       name="Slack mention → triage",
       description="Разбирает упоминания в Slack и заводит задачу.",
       triggers=(triggers.SLACK_MENTION,),
       agent={"backend": "claude_cli", "model": "sonnet"},
       prompt_path="prompts/slack_triage.md",
       workspace="ephemeral",   # см. таблицу ниже
   )

   AUTOMATIONS: list[Automation] = [DEV_TASK, TG_CHAT, PR_REVIEW, SLACK_TRIAGE]
   ```

3. **Выбрать `workspace`** (одно поле — один дискриминатор):

   | Значение | Когда брать |
   |---|---|
   | `git_worktree` | Нужно открыть PR в `TARGET_REPO` от свежей ветки. |
   | `pr_worktree` | Нужно проинспектировать существующий PR на его `head_sha`. |
   | `fixed` | Нужен стабильный cwd (например, для Claude CLI `--resume`). Обязательно укажи `cwd=Path(...)` — `__post_init__` бросит `ValueError`, если забудешь. |
   | `ephemeral` | Дефолт. Просто writable tmpdir под `WORKTREE_ROOT/run-<id>/`. |

4. **`session_key`** — опциональный `Callable[[Event], str | None]`. Если
   возвращает непустую строку, оркестратор схлопнёт все run-ы с тем же
   ключом в одну агентную сессию (Claude CLI `--resume`). Примеры:
   `tg_chat` склеивает по `chat_id`, `pr_review` — по `repo#number`.
   Возвращай `None`, чтобы каждое событие шло в свежую сессию.

5. **Скиллы.** Никакого per-automation whitelist'а нет: агент видит весь
   `SKILL_REGISTRY` (`commit_and_push_pr` / `telegram_reply` /
   `wait_for_human`) плюс `call_subagent`. Если для фичи нужен новый
   skill — добавляй его в [`src/foundry/skills/`](../../src/foundry/skills/)
   и регистрируй в `SKILL_REGISTRY`. Реальные side-effect'ы и security
   boundaries — в skill, остальное (gh / git / pytest / fs) агент дёргает
   через `Bash` сам.

6. **Терминальный статус.** Промпт обязан заканчиваться маркером:

   - `STATUS: done` → `RunStatus.DONE`.
   - `STATUS: approved | change_requested | rejected` → `RunStatus.DONE`
     с `outcome` (используется `pr_review`).
   - `STATUS: failed[:<kind>]` → `RunStatus.FAILED`,
     `kind ∈ {deterministic, acceptance, infra, dangerous, unclear}`.
   - Без маркера / неизвестное слово → `RunStatus.UNCLEAR`.

   См. [`status_marker.py`](../../src/foundry/status_marker.py).

7. **Тесты:**

   - Юнит на реестр: что новая запись имеет правильные триггеры,
     `workspace`, что `__post_init__` ловит инвариант. Пример —
     [`tests/test_automations_registry.py`](../../tests/test_automations_registry.py).
   - E2E: характеризационный сценарий со `StubAgent`, что run пишет
     ожидаемый набор `run_events` и финиширует в нужный статус. Пример —
     [`tests/test_characterization_automations.py`](../../tests/test_characterization_automations.py).
   - При необходимости интеграционный тест с реальным dispatch'ем
     события — [`tests/test_orchestrator_integration.py`](../../tests/test_orchestrator_integration.py).

8. **Перепрогон `pytest`.** Если ничего не сломалось и характеризационные
   тесты зелёные — можно поднимать `serve` и наблюдать в UI.

### Гайд по решениям

- **Несколько триггеров в одной automation** (например, PR_REVIEW
  слушает и `review_requested`, и `authored`) — допустимо, всё это в
  один `triggers=(...)`-кортеж.
- **Сессии.** Если разговор многоходовой — нужен `session_key` и
  `workspace="fixed"` со стабильным `cwd` (Claude CLI индексирует
  `--resume` по хешу cwd).
- **Воркфлоу с ожиданием человека** — пусть промпт зовёт
  `wait_for_human(...)` через MCP. Run перейдёт в `WAITING`. Отдельный
  event разбудит run заново — оркестратор продолжит в той же сессии.
- **Cron-триггеры.** Это отдельная история: правило живёт в
  [`listeners/cron_rules.py`](../../src/foundry/listeners/cron_rules.py),
  triggers получают вид `cron.<rule_id>`, и automation подписывается
  через `triggers=(f"cron.{RULE_ID}",)`. `validate_registry` примет
  только те cron-id, что реально зарегистрированы.

---

## Чек-лист перед PR

- [ ] `uv run pytest` зелёный.
- [ ] Новый `trigger_id` в `triggers.ALL` (если listener) или
      `cron_rules.py` (если cron-правило).
- [ ] Listener выставляет `id` / `source` / `listen` и emit-ит через
      `EmitFn`, не лезет в `state.py`.
- [ ] Automation подписана через `foundry.triggers.<NAME>`, а не
      строковым литералом.
- [ ] `Automation.workspace` соответствует тому, что реально нужно
      агенту; `fixed` — с обязательным `cwd`.
- [ ] Промпт заканчивается явным `STATUS:`-маркером.
- [ ] Новые env-переменные есть в `.env.example`.
- [ ] При новых side-effect'ах — добавлен skill, не «прячем» бизнес в
      `agents/`.
