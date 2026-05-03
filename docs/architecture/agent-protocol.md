# Agent Protocol — план

Цель — ввести agent-agnostic слой между стадией `implement` и конкретным coding-агентом (claude CLI, aider, stub). Остальные стадии (`plan`, `verify`, `pr`) протокола не касаются.

## Что НЕ делаем в этой итерации

- Retry-loop (Day 5–6). Протокол закладывает `prev_attempts`, но pipeline не заполняет.
- Streaming наружу (foundry не UI).
- Session continuity (`--resume`). Каждый вызов stateless.
- Cost cap / turn cap как gate. Токены только фиксируем в logs.
- Langfuse. В логи пишем раздельно, инструментация позже.
- Agent выбирает модель / провайдера — это его внутренняя настройка.

## Контракт

```python
# src/foundry/agents/base.py

@dataclass(frozen=True)
class AgentAttempt:
    summary: str          # что агент сказал в прошлой попытке
    diff: str             # diff который тогда получился (может быть пустой)
    verify_stderr: str    # почему verify его отверг

@dataclass(frozen=True)
class AgentInput:
    issue_title: str
    issue_body: str
    prev_attempts: list[AgentAttempt]   # [] на первом вызове

@dataclass(frozen=True)
class AgentOutcome:
    success: bool
    summary: str                    # финальный текст агента
    changed_files: list[str]        # из `git status --porcelain` (ground truth)
    cost_usd: float | None
    tokens_in: int | None
    tokens_out: int | None
    raw_events: list[dict]          # для logs_json (дебаг)

class CodingAgent(Protocol):
    name: str
    def apply(self, inp: AgentInput, worktree: Path, timeout_sec: int) -> AgentOutcome: ...
```

**Инварианты:**

- `apply()` НЕ коммитит — это работа `pr` стадии.
- `apply()` НЕ создаёт/чекаутит ветки — worktree уже на нужной ветке.
- `changed_files` берём из git, не от агента — ground truth, работает для любой реализации.
- `success=False` означает "агент не справился" (пустой diff, отказ, no-op). `ShellError`/таймаут пробрасываем как исключение (retriable infra-fail).
- Sync API. `subprocess.run(..., timeout=N, capture_output=True)`, JSONL парсим по факту.

## Реализации

### 1. `StubAgent` (default, offline)

Перенос текущего `implement.run` поведения: append_line в README. Нужен чтобы:
- CI/тесты работали без API-ключей.
- Можно было дебажить pipeline без LLM.
- `CODING_AGENT=stub` — zero external deps.

### 2. `ClaudeCliAgent`

```
claude -p <prompt>
  --output-format stream-json --verbose
  --dangerously-skip-permissions
  --max-turns 30
```

- `subprocess.run(cwd=worktree, timeout=timeout_sec, capture_output=True)`.
- stdout — JSONL, парсим построчно.
- Из `system` события → `session_id` (в raw_events, не обязательно использовать).
- Из `assistant.message.usage` → токены (input + cache_read + cache_creation для input, output_tokens для output).
- Из `result` события → final text, final usage, `total_cost_usd`.
- `changed_files` — `git -C worktree status --porcelain | parse`.
- `success` — есть ли non-empty diff И result.subtype == "success".

Auth: подписка Pro/Max через `claude login` (один раз, CLI держит).

### 3. `AiderCliAgent`

```
aider --message <prompt>
  --yes-always --no-auto-commits --no-stream --no-check-update
  --no-show-model-warnings --no-gitignore
  --model <settings.agent_model>
```

- `subprocess.run(cwd=worktree, timeout=timeout_sec, capture_output=True)`.
- stdout текстовый, а не JSON. Парсим:
  - `Tokens: 2.7k sent, 105 received. Cost: $0.0017 message` — regex.
  - `Applied edit to <file>` / `No changes to make` — для success-детекта.
- `changed_files` — опять же из `git status --porcelain`.
- Если нужны файлы явно — можно добавить `--file` на основе `issue_body` (опционально, пока не делаем — полагаемся на repomap).

Auth: OpenRouter API key (живёт в `~/.aider.conf.yml` после OAuth, либо `OPENROUTER_API_KEY` env).

## Промты — в отдельных файлах

```
src/foundry/agents/prompts/
  claude_cli.task.md      # первый вызов
  claude_cli.retry.md     # для retry (Day 5–6; пока не вызывается)
  aider_cli.task.md
  aider_cli.retry.md
```

Формат — простой `.format(**placeholders)`. Плейсхолдеры:
`{issue_title}`, `{issue_body}`, `{prev_diff}`, `{prev_stderr}`, `{prev_summary}`.

Почему раздельно по агентам: их оптимальные промты различаются (aider хочет "edit these files to...", Claude — "analyze the repo and...").

### Черновик `claude_cli.task.md`

```
You are working inside a git repository. A GitHub issue describes a change that needs to be made.

## Issue title
{issue_title}

## Issue body
{issue_body}

## What to do
1. Explore the repository to understand the codebase.
2. Make the minimal set of changes needed to address the issue.
3. Do NOT commit or push — just modify files in the working tree.
4. When done, print a one-paragraph summary of what you changed and why.

Constraints:
- Match existing code style.
- No speculative refactoring. Only touch what the issue requires.
- If the issue is ambiguous, pick the simplest reasonable interpretation and mention it in the summary.
```

### Черновик `aider_cli.task.md`

```
{issue_title}

{issue_body}

Please make the minimal set of edits needed to address this. Match existing code style.
Do not add speculative changes or refactoring beyond what is asked.
```

(Короче, потому что aider сам накатит свою системку поверх.)

### Черновик `claude_cli.retry.md` (заготовка, не используется в этой итерации)

```
The previous attempt at this issue failed verification.

## Original issue title
{issue_title}

## Original issue body
{issue_body}

## Your previous summary
{prev_summary}

## Diff you produced last time
```diff
{prev_diff}
```

## Verify output (stderr)
```
{prev_stderr}
```

Please fix the failure and retry. You may revert your previous changes entirely and take a different approach.
```

## Factory и конфиг

```python
# src/foundry/agents/factory.py
def make_agent(settings: Settings) -> CodingAgent:
    match settings.coding_agent:
        case "stub": return StubAgent()
        case "claude_cli": return ClaudeCliAgent(settings)
        case "aider": return AiderCliAgent(settings)
        case other: raise ConfigError(f"unknown CODING_AGENT={other}")
```

Новые env переменные (в `config.py`):

```
CODING_AGENT=stub              # stub|claude_cli|aider, default=stub
AGENT_TIMEOUT_SEC=600
AGENT_MODEL=openrouter/google/gemini-3-flash-preview   # для aider; claude_cli игнорит
```

Default `stub` — чтобы текущие тесты и `uv run foundry run` продолжали работать без внешних зависимостей.

## Изменения в `implement.py`

```python
def run(task: Task, plan: dict, worktree_path: Path, settings: Settings) -> dict:
    agent = make_agent(settings)
    inp = AgentInput(
        issue_title=task.issue_title,
        issue_body=task.issue_body,
        prev_attempts=[],   # Day 5–6 заполнит из task.logs_json
    )
    outcome = agent.apply(inp, worktree_path, settings.agent_timeout_sec)
    if not outcome.success:
        raise RuntimeError(f"agent failed: {outcome.summary}")
    return asdict(outcome)    # ложится в logs_json
```

`plan` аргумент остаётся в сигнатуре, но не используется в этой итерации. Стадия `plan.run` пока возвращает пустой `{}` (или остаётся hardcoded для обратной совместимости со Stub — подумать).

## Что ломается из текущего кода

- `tests/test_implement.py` (4 теста на `append_line`) — переезжают в `tests/test_stub_agent.py` или удаляются (поведение переносится в Stub, тесты могут упроститься).
- `stages/implement.py` класс `UnsupportedAction` — не нужен больше (Stub проверку делает внутри).
- `stages/plan.py` возвращаемый формат `{steps: [...]}` — устаревает. На первой итерации возвращает `{}`, в будущем — `{goal, acceptance, hints}` (LLM-план, Day 3b).

## Тесты

- `test_stub.py` — end-to-end: Stub на tmp worktree, появляется строка в README.
- `test_claude_cli.py` — мокаем `subprocess.run`, подаём фиксированный stream-json, проверяем парсинг (токены, session_id, summary, success).
- `test_aider_cli.py` — мокаем `subprocess.run`, подаём фиксированный stdout, проверяем regex-парсинг токенов и success-детект.
- `test_pipeline.py` — уже мокает `implement_stage.run`, ломаться не должен.

Живой e2e тест на OpenRouter — руками через `scripts/add-and-process.sh` после переключения `CODING_AGENT=aider`.

## Порядок реализации (checkboxes)

- [ ] `agents/base.py` — Protocol + dataclasses
- [ ] `agents/stub.py` — перенос текущей логики `append_line`
- [ ] `agents/factory.py` + новые поля в `config.py` (`CODING_AGENT`, `AGENT_TIMEOUT_SEC`, `AGENT_MODEL`)
- [ ] `implement.py` — делегирование агенту
- [ ] `test_stub.py` — зелёные тесты
- [ ] `agents/prompts/claude_cli.task.md` + `agents/claude_cli.py`
- [ ] `test_claude_cli.py` — мок subprocess
- [ ] Живой прогон: `CODING_AGENT=claude_cli` + `./scripts/add-and-process.sh`
- [ ] `agents/prompts/aider_cli.task.md` + `agents/aider_cli.py`
- [ ] `test_aider_cli.py` — мок subprocess
- [ ] Живой прогон: `CODING_AGENT=aider` + `./scripts/add-and-process.sh`
- [ ] Обновить CLAUDE.md / DEBUG.md: раздел про агенты, env-переменные, как выбирать

## Открытые вопросы (к тебе)

1. `plan` стадия — оставляем пустым (`return {}`) или сносим из pipeline? Сейчас предлагаю оставить — как хук для будущего LLM-планировщика, Day 3b.
2. Prompt для Claude CLI — в черновике я попросил "explore the repository". Есть риск, что на крупной задаче агент будет грепать/читать часами. Задать `--max-turns 30` или агрессивнее (15)?
3. Аутентификация aider через OpenRouter — мы завязываемся на OAuth в `~/.aider.conf.yml`. На чужой машине (CI) надо будет через `OPENROUTER_API_KEY`. Документируем оба пути?
4. `StubAgent` сохранять или убрать после реализации реальных? Я за сохранить — бесплатный smoke-тест для CI.
