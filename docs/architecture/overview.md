# Foundry — architecture overview

Карта проекта в схемах. Три центральных понятия: **Trigger/Event**,
**Automation**, **Run**. Всё остальное — обвязка вокруг них.

## Поток данных: от внешнего мира до side-effect

```mermaid
flowchart LR
    subgraph EXT["External sources"]
        gh_issue["GitHub issues"]
        gh_pr["GitHub PRs"]
        tg["Telegram bot"]
        cron_t["Cron"]
        discord["Discord"]
    end

    subgraph LIS["Listeners (long-running asyncio)"]
        gh_iss_l["GithubIssuesListener"]
        gh_pr_l["GithubPrReviewListener"]
        tg_l["TelegramListener"]
        cron_l["CronListener"]
        discord_l["DiscordListener"]
    end

    subgraph DIS["Dispatcher — events.py"]
        emit["EmitFn — trigger_id, dedupe_key, payload"]
        dispatch_event["dispatch_event<br/>INSERT events row<br/>+ INSERT runs PENDING<br/>per matched automation"]
    end

    subgraph DB["SQLite — state.py"]
        events_tbl["events<br/>UNIQUE trigger_id, external_id"]
        runs_tbl["runs<br/>PENDING / RUNNING / WAITING<br/>DONE / FAILED / UNCLEAR"]
        run_events_tbl["run_events<br/>append-only breadcrumbs"]
    end

    subgraph ORCH["Orchestrator — orchestrator.py"]
        loop["run_forever loop"]
        claim["claim_pending_run<br/>atomic UPDATE RETURNING"]
    end

    subgraph RUN["Runner — runner.py"]
        prepare["_prepare_workspace<br/>match automation.workspace"]
        spawn["spawn agent"]
        parse["parse STATUS marker"]
        finish["finish_run"]
    end

    subgraph AGT["Agent — agents/"]
        cli["claude_cli / codex_cli<br/>opencode_cli / stub"]
        mcp_box["per-run MCP server<br/>mcp/server.py"]
    end

    subgraph SK["Skills — skills/"]
        commit_pr["commit_and_push_pr"]
        tg_reply["telegram_reply"]
        wait["wait_for_human"]
        sub["call_subagent (recursive)"]
    end

    gh_issue --> gh_iss_l
    gh_pr --> gh_pr_l
    tg --> tg_l
    cron_t --> cron_l
    discord --> discord_l

    gh_iss_l --> emit
    gh_pr_l --> emit
    tg_l --> emit
    cron_l --> emit
    discord_l --> emit

    emit --> dispatch_event
    dispatch_event --> events_tbl
    dispatch_event --> runs_tbl

    loop -->|polls + wake event| claim
    runs_tbl -->|PENDING rows| claim
    claim --> prepare
    prepare --> spawn
    spawn --> cli
    cli <-->|tools| mcp_box
    mcp_box --> commit_pr
    mcp_box --> tg_reply
    mcp_box --> wait
    mcp_box --> sub
    sub -.recurse.-> cli
    cli -->|final reply with STATUS marker| parse
    parse --> finish
    spawn -.streams.-> run_events_tbl
    finish --> runs_tbl
```

Ключевые инварианты:

- **Один write-path в очередь.** `events.dispatch_event` — единственное
  место, где появляется `events` row + `PENDING` runs. И листенеры,
  и API-retry, и `call_subagent` ходят через него.
- **`runs(status='pending')` — это и есть очередь.** Никакого отдельного
  курсора. Восстановление после рестарта = `recover_orphan_runs` (помечает
  висящие `RUNNING` как `FAILED/INFRA`).
- **Run завершается по маркеру в финальной реплике агента**
  (`STATUS: done|approved|change_requested|rejected|failed[:kind]`),
  а не по MCP-инструменту.

## Модули и направление зависимостей

```mermaid
flowchart TD
    cli["foundry.cli<br/>serve / runs"]
    api["src/api/<br/>FastAPI + SSE"]
    web["web/<br/>Vite + React"]

    orch["foundry.orchestrator"]
    runner["foundry.runner"]
    events["foundry.events<br/>dispatch_event"]
    state_mod["foundry.state<br/>raw SQL"]

    listeners_mod["foundry.listeners<br/>github_issues, github_pr_review<br/>telegram, cron, discord"]
    triggers_mod["foundry.triggers"]
    automations_mod["foundry.automations.registry"]

    agents_mod["foundry.agents<br/>claude_cli, codex_cli<br/>opencode_cli, stub"]
    skills_mod["foundry.skills<br/>pr / telegram_reply<br/>wait_for_human"]
    mcp_mod["foundry.mcp<br/>server, runner, config"]

    workspace["foundry.worktree<br/>foundry.pr_worktree"]
    status_mod["foundry.status_marker"]
    config_mod["foundry.config"]
    models_mod["foundry.models"]
    shell_mod["foundry.shell"]

    cli --> orch
    cli --> listeners_mod
    cli --> events
    cli --> config_mod

    api --> state_mod
    api --> events
    web -.HTTP / SSE.-> api

    orch --> runner
    orch --> state_mod

    runner --> agents_mod
    runner --> mcp_mod
    runner --> workspace
    runner --> status_mod
    runner --> state_mod
    runner --> automations_mod

    listeners_mod --> triggers_mod
    listeners_mod --> events

    events --> automations_mod
    events --> state_mod

    automations_mod --> triggers_mod
    automations_mod --> models_mod

    agents_mod --> models_mod
    agents_mod --> events

    skills_mod --> state_mod
    skills_mod --> shell_mod

    mcp_mod --> skills_mod
    mcp_mod --> events
```

Стрелка `A → B` читается как «A импортирует B». Циклов нет; ядро —
`state` / `events` / `models`, к ним сходятся почти все.

## Жизненный цикл одного run

```mermaid
stateDiagram-v2
    [*] --> PENDING: dispatch_event
    PENDING --> RUNNING: claim_pending_run
    RUNNING --> WAITING: skill wait_for_human
    WAITING --> RUNNING: human reply or new event
    RUNNING --> DONE: STATUS done / approved / change_requested / rejected
    RUNNING --> FAILED: STATUS failed or runner exception
    RUNNING --> UNCLEAR: no or unknown STATUS marker
    FAILED --> PENDING: POST /api/runs/id/retry
    DONE --> [*]
    UNCLEAR --> [*]
```

`outcome` (`approved` / `change_requested` / `rejected`) — это смысловой
вердикт `pr_review`, лежит рядом со статусом `DONE`; жизненный цикл
успешный.

## Workspace-дискриминатор

`Automation.workspace: Literal["git_worktree", "pr_worktree", "fixed", "ephemeral"]`
определяет, в каком каталоге запустится агент. Раздаётся в
[`runner._prepare_workspace`](../../src/foundry/runner.py) одним
`match`-ом:

| Значение | Где живёт | Кто использует | Зачем |
|---|---|---|---|
| `git_worktree` | `WORKTREE_ROOT/task-<run_id>` на ветке `foundry/task-<run_id>` | `dev_task` | Изоляция веток для PR. |
| `pr_worktree` | под `pr_review_base_path` на `head_sha`, rsync-овый overlay для untracked-конфигов | `pr_review` | Воспроизвести состояние PR локально. |
| `fixed` | `cwd` из реестра | `tg_chat` | Claude CLI индексирует `--resume` сессии по хешу cwd — нужен стабильный путь. |
| `ephemeral` | `WORKTREE_ROOT/run-<run_id>/` | cron / utility | Просто нужен writable tmpdir. |

## Дальше

- [extending.md](extending.md) — как добавить новый listener или
  automation шаг за шагом.
- [agent-protocol.md](agent-protocol.md) — исторический документ про
  staged-pipeline (≤ C2). Текущий контракт агента — в
  [src/foundry/agents/CLAUDE.md](../../src/foundry/agents/CLAUDE.md).
- [simplify-2026-05.md](simplify-2026-05.md) — журнал последней
  упрощающей итерации (убран `AgentStage`, схлопнут `workspace`,
  выделен `runner.py`).
