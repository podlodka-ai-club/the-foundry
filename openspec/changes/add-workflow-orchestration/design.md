## Context

Текущий `pipeline.py` последовательно выполняет один сценарий: получить issue, подготовить worktree, вызвать `context`, `plan`, `implement`, `verify`, открыть PR и отметить задачу завершённой. Состояние задачи хранится в SQLite `tasks`, а UI опирается на append-only `task_events`. Это хорошая база: уже есть persistence, observability и stage boundaries.

Проблема в том, что будущие режимы из `IDEAS.md` имеют разные входы и разные окончания:

- labeled issue запускает полный dev-cycle;
- PR comment/manual request запускает только verify/report;
- Discord intent может сначала искать похожие задачи или создавать issue;
- planner в будущем может отказаться, попросить вводные или разбить задачу на части;
- deploy и merge conflict resolution — это отдельные workflow, а не просто дополнительные строки в текущем линейном коде.

## Goals / Non-Goals

**Goals:**

- Ввести маленький локальный workflow runner без внешнего graph runtime.
- Оставить существующий `foundry run` совместимым: он всё ещё обрабатывает labeled issues.
- Сделать `dev_task` первым workflow и добавить внутри него bounded retry-loop `implement -> verify`.
- Добавить второй workflow `pr_verify` как проверку архитектуры: тот же verifier, но другой вход и другой выход.
- Сохранить `task_events` и `logs_json` совместимыми с существующей UI/API моделью.
- Заложить typed outcomes для будущих возможностей: `needs_input`, `declined`, `decompose`, `parallel_candidates`, `review_required`.

**Non-Goals:**

- Не внедрять LangGraph в этой итерации.
- Не делать полноценную очередь событий, webhook receiver или Discord bot.
- Не реализовывать параллельные агенты, декомпозицию, deploy, merge conflict resolution и agentic code review прямо сейчас.
- Не менять модель GitHub issue fetching как часть этой итерации.
- Не делать PR checkout из GitHub обязательной частью первого `pr_verify`; достаточно workflow entrypoint'а, который может работать с предоставленным task/worktree-контекстом. Полный `checkout_pr` можно добавить следующим изменением.

## Decisions

### 1. Локальный workflow runner вместо LangGraph

Первый runner должен быть обычным Python-кодом вокруг существующих stage-функций. Он должен знать имя workflow, текущий step, попытки и переходы, но не должен заменять `task_events` собственным источником правды.

Альтернатива: сразу использовать LangGraph. Это даст богатую graph-модель, но создаст второй state runtime рядом с SQLite/events. Пока текущие требования укладываются в простой runner, это лишняя сложность.

### 2. `dev_task` остаётся основным workflow

Существующий issue-driven сценарий становится `dev_task`:

```text
fetch -> context -> plan -> attempt_loop -> pr -> done

attempt_loop:
  implement(attempt_context)
  verify
  pass                     -> exit loop
  retryable fail + budget  -> implement again
  needs human              -> blocked/failed
  terminal fail            -> failed
```

В первом implementation pass это можно сделать без новой таблицы workflow instances: `tasks.current_stage`, `tasks.status`, `tasks.attempts`, `logs_json` и `task_events` уже дают достаточно состояния. Если понадобится несколько workflow на одну task или child tasks, тогда стоит добавить отдельную таблицу `workflow_runs`.

### 3. Retry-loop является контролируемым quality gate

Verifier не должен просто бросать `RuntimeError("verify failed")`. Он должен возвращать структурированный результат:

```python
{
    "passed": bool,
    "retryable": bool,
    "requires_human": bool,
    "failure_kind": "deterministic" | "acceptance" | "infra" | "unclear" | "dangerous",
    "report": "...",
}
```

`dev_task` принимает решение о переходе, а не verifier и не implement agent. Это важно для качества: агент не может бесконечно латать задачу и не может сам решить, что опасную ситуацию можно игнорировать.

### 4. Следующая implementation attempt получает verifier feedback

Повторная реализация должна получать не только исходный план, но и feedback предыдущей проверки:

```text
original issue
plan / acceptance criteria
attempt number
previous implement summary
previous verify report
failed checks
```

Минимальный способ: расширить input в `agent_implement.run(...)` через дополнительные поля в `plan` dict или отдельный `attempt_context` dict, не ломая существующую сигнатуру stage. Более чистый вариант для follow-up — ввести typed DTO для stage inputs.

### 5. `pr_verify` — отдельный workflow, а не ветка `dev_task`

`pr_verify` использует verifier, но отличается по смыслу:

```text
checkout/load PR context -> verify -> write/report PR comment
```

В первом scope можно реализовать entrypoint вида `run_pr_verify(settings, task, worktree_path, comment_context=None) -> dict`, который:

- ставит stage `verify`;
- вызывает тот же `verify_stage.run`;
- пишет `task_events`;
- не вызывает `pr_stage.run`;
- не меняет задачу в `done`;
- возвращает report для будущей стадии comment.

Полная интеграция с GitHub PR comments и branch checkout остаётся отдельной задачей.

### 6. Planner outcomes фиксируются как future-facing contract

Planner в будущем может вернуть:

- `plan_ready`: можно выполнять;
- `needs_input`: надо запросить уточнения;
- `declined`: задача не должна выполняться;
- `decompose`: надо создать child tasks;
- `strategy`: выбрать workflow/model mix для bugfix/feature/refactor.

Но эти outcomes не являются произвольным графом от агента. Orchestrator валидирует outcome и исполняет только allowlisted transitions.

## Risks / Trade-offs

- Риск: локальный runner постепенно превратится в самописный LangGraph. Mitigation: держать runner простым; если появятся вложенные graph state, parallel branches и human checkpoints, отдельно пересмотреть LangGraph.
- Риск: `tasks.attempts` сейчас означает task attempts, а не implement attempts. Mitigation: для первой версии фиксировать implement attempt в event payload/logs; отдельное поле или таблицу добавлять только когда UI/runner начнут от этого зависеть.
- Риск: `pr_verify` без полноценного checkout PR выглядит неполным. Mitigation: это осознанный slice для проверки workflow separation; GitHub integration вынести в отдельный `checkout_pr` stage.
- Риск: verifier output от agent backend может быть неструктурированным. Mitigation: normalize в `verify_stage.run`, с conservative defaults (`retryable=False` для непонятного результата).
- Риск: retry-loop может скрывать плохой план. Mitigation: максимум 2-3 попытки; `requires_human`/`terminal` останавливают цикл; все попытки сохраняются в events.

## Migration Plan

1. Добавить workflow helpers без изменения внешнего поведения `foundry run`.
2. Перенести текущую последовательность `_process_task` в `dev_task` helper с теми же событиями.
3. Добавить bounded attempt-loop и тесты на pass-after-retry, exhausted retries, human-blocked verification.
4. Добавить `pr_verify` entrypoint и тест, что он вызывает verify/report, но не открывает PR.
5. Сохранить rollback простым: если workflow helpers окажутся неудачными, можно вернуть вызовы стадий обратно в `pipeline.py`, потому что stage contracts остаются прежними.

## Open Questions

1. Нужен ли отдельный `TaskStatus.BLOCKED`, или пока `FAILED` с `requires_human=True` в event/log достаточно?
2. Где хранить `max_implement_attempts`: env (`MAX_IMPLEMENT_ATTEMPTS`), `Settings`, или workflow definition?
3. Должен ли `pr_verify` сразу писать GitHub comment, или сначала возвращать report, а comment stage добавить отдельно?
4. Когда вводить отдельную таблицу `workflow_runs`: сейчас, или только при появлении нескольких workflow на одну task / child tasks?
