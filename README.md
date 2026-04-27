# The Foundry

Проект в рамках **Hacker Sprint #1: Фабрика фичей** (https://www.notion.so/Hacker-Sprint-1-33f2db4c860e8064a657e199b4578f66?source=copy_link).

End-to-end pipeline: GitHub Issue → CONTEXT → PLAN → IMPLEMENT (через aider) → VERIFY → PR.

## Docs
Документы, логи встреч и прочие текстовые артефакты храним в папке `/docs`.

## Что нужно сделать вручную до первого прогона
1. `brew install uv gh`
2. `gh auth login` — токен с правом `repo`.
3. Создать на GitHub sandbox-репо (например, `the-foundry-sandbox`), лейбл `agent-task`, 1–2 issue.
4. `cp .env.sample .env`, заполнить `SOURCE_REPO`, `TARGET_REPO` и API-ключ выбранного `CODING_LLM`.
5. `uv sync && uv run foundry run` — ожидаемый результат: aider обработает каждый issue в worktree и в sandbox появится PR.

## Coding agent

Стадия IMPLEMENT использует [aider](https://aider.chat/) с одним из LLM-провайдеров:

```
CODING_LLM=DEEPSEEK | ANTHROPIC | CHATGPT
DEEPSEEK_API_KEY=...        # или ANTHROPIC_API_KEY / OPENAI_API_KEY
DEEPSEEK_MODEL_NAME=...     # опционально, переопределяет дефолт провайдера
AIDER_TIMEOUT_SECONDS=600
```

Aider запускается с `--yes-always --no-git`: автоконфирмит изменения файлов, но git-операции остаются за PR-стадией pipeline.

Модуль `src/foundry/coding_agent/` содержит:
- `runner.py` — функция `run_aider(...)` для вызова aider в worktree.
- `providers/` — абстракция LLM-провайдеров (DeepSeek/Anthropic/ChatGPT) c фабрикой `LLMProviderFactory.create_from_settings(settings)`. Новый провайдер добавляется наследованием `BaseLLMProvider` и регистрацией в `LLMProviderFactory`.

## Команды

```
make run          # один прогон pipeline
make test         # все тесты
make test-unit    # быстрые unit-тесты
```
