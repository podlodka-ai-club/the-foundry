# PR review automation — план

Автоматизация `pr_review`, реагирующая на события listener'а `github_pr_review`.
Цель: для каждого PR (и каждого нового push'а в него) разворачивать локальную
копию кода на нужном SHA, давать агенту читать контекст и оставлять текст ревью
в `run_events` для просмотра в UI. **Без авто-постинга в GitHub, без коммитов.**

## Объём v1

- Триггер: оба kind'а от `github_pr_review` — `pr.review_requested` и `pr.authored`.
- Агент: `claude_cli` / `sonnet` (как в `dev_task`).
- Один worktree на run, отдельный per-PR-per-push.
- Несколько push'ей в один PR → разные run'ы, **связанные через единый `session_id`**.
- Никаких записей обратно в GitHub (ни ревью, ни комментариев, ни реакций).

## Discovery: repo → локальный путь

Один env: `PR_REVIEW_BASE_PATH=~/w/datura/lium/main` (umbrella-папка, не git-репо).

На запуске listener-а / лениво при первом обращении — пройти `base.rglob(".git")`,
для каждого вычитать `git remote get-url origin`, нормализовать в `owner/name`,
кэшировать в памяти процесса. Если PR прилетел для repo, которого нет в карте —
run падает с `failure_kind=infra` и сообщением `no local checkout for {repo} under {base}`.

Структура umbrella (подтверждена осмотром):
```
~/w/datura/lium/main/                        ← umbrella, сам не git-репо
├── CLAUDE.md                                ← 240 строк, untracked, общий контекст
├── lium-core/        → Datura-ai/lium-core
├── lium-io/          → Datura-ai/lium-io
├── compute-app/      → Datura-ai/compute-app
├── compute-app-v2/   → Datura-ai/compute-app-v2
├── lium-miner-portal/, lium-miner-portal-frontend/, ...
└── chutes/chutes-miner/ → chutesai/chutes-miner
```

## Worktree: гибрид `git worktree` + `rsync`

```bash
base=$(repo_map[repo])           # ~/w/datura/lium/main/lium-io
umbrella=$PR_REVIEW_BASE_PATH    # ~/w/datura/lium/main
target=$umbrella/_foundry-pr-${run_id}-${repo_short}

# 1) worktree от base — только tracked файлы PR на нужном SHA, без node_modules/.venv
git -C "$base" fetch origin <head_sha>
git -C "$base" worktree add --detach "$target" <head_sha>

# 2) rsync поверх — untracked локальные конфиги и заметки
rsync -a \
  --include='*/' \
  --include='*.md' \
  --include='.claude/***' \
  --include='.agents/***' \
  --exclude='*' \
  "$base/" "$target/"
```

Worktree кладём **сиблингом umbrella** (`umbrella/_foundry-pr-...`), чтобы Claude Code
при walk-up автоматически подхватывал umbrella `CLAUDE.md` (находится прямо над cwd).
Иерархия CLAUDE.md, которую увидит агент:

```
$target/CLAUDE.md                              ← rsync'нут из base/lium-io
$target/.claude/                               ← rsync'нут
~/w/datura/lium/main/CLAUDE.md                 ← umbrella, walk-up
~/.claude/CLAUDE.md                            ← глобальный
```

Cleanup на терминальном статусе run'а (`mark_done` / `mark_failed` / `FAILED` от
оркестратора): `git -C "$base" worktree remove --force "$target"`. Если worktree
прибит руками — fallback `rm -rf "$target"`.

## Session linking

Расширяем `Automation`:

```python
@dataclass(frozen=True)
class Automation:
    ...
    session_key: Callable[[Event], str | None] | None = None
```

Для `pr_review`:
```python
session_key=lambda ev: f"{ev.payload['repo']}#{ev.payload['number']}"
```

Оркестратор при создании Run'а: если `automation.session_key` задан — найти
последний Run этой автоматизации с тем же ключом (вычисленным из его
`event.payload`) и переиспользовать `session_id`. Иначе — fallback на текущее
поведение (новая session per event).

`external_id` listener-а **остаётся** `{repo}#{number}@{sha}` — это нужно для DB-level
дедупа push'ей. session_id и external_id живут на разных уровнях.

## Скиллы

Новый: `open_pr_worktree` — читает env `FOUNDRY_PR_REPO`, `FOUNDRY_PR_HEAD_SHA`,
`FOUNDRY_RUN_ID`, `PR_REVIEW_BASE_PATH`, делает discovery → worktree → rsync,
возвращает `{worktree, repo, head_sha, base_local_path}`. Регистрирует cleanup
hook (worktree remove на терминальном статусе).

Существующие используем как есть: `mark_done`, `mark_failed`, `react_emoji`,
`call_subagent`, `mark_milestone`, `compact_context`. **Не даём** `commit_and_push_pr`,
`run_tests` (агенту это незачем для read-only ревью; если позже захотим — добавим).

Скилла "запостить ревью" в v1 нет — текст ревью идёт в `mark_done(summary=...)`,
читается через UI.

## Промпт (черновик `prompts/pr_review.md`)

```
You are reviewing PR #{number} in {repo} at SHA {head_sha} (author: {author}).
URL: {url}.

Your worktree contains the PR's code already checked out at the head SHA.
Untracked CLAUDE.md / .claude / .agents from the developer's local checkout
have been rsynced over — read them for project conventions.

The umbrella folder one level up has a high-level CLAUDE.md describing how
this repo fits into the larger project — Claude Code loads it via walk-up.

Steps:

1. Get the diff:
   - `gh pr diff {number} --repo {repo}` for the unified diff, OR
   - `git log --oneline {base_ref}..HEAD` + `git diff {base_ref}...HEAD` if you
     prefer per-file walking.

2. Explore for context: read changed files in full, their callers, related
   tests, and any module-level CLAUDE.md.

3. Identify issues — bugs, logic errors, missing tests, style/convention
   violations vs CLAUDE.md, security concerns. Skip nitpicks.

4. {prior_review_block — if previous run for this PR exists, paste its summary
    and ask: "Compared to the previous push, what changed? Were prior
    suggestions addressed?"}

Output via mark_done(summary=...) with this structure:

## Summary
<2-3 sentences: what the PR does, your overall verdict>

## Issues
- [path:line] [priority] description

## Suggestions
- ...

## Notes for the author
<optional, if anything human-readable beyond issues>

DO NOT commit, push, or post anything to GitHub. Read-only review.
```

## Безопасность / не делаем

- Никаких `git commit` / `git push` в worktree.
- Никаких `gh pr review` / `gh pr comment`.
- Никаких изменений в базовом чекауте юзера (`base`).
- `.env` и подобные секреты НЕ rsync'аем (rsync includes только `*.md`, `.claude/`,
  `.agents/`).

## Чек-лист реализации

- [x] `Automation.session_key` — поле + резолв в `_create_and_dispatch`.
- [x] `Automation.pr_worktree` — новый флаг (4-й режим в `_prepare_worktree`).
- [x] `src/foundry/pr_worktree.py` — discovery `repo → path` (depth ≤ 2),
  `prepare_pr_worktree` (`git fetch` + `worktree add --detach` + `rsync`),
  cleanup-callback.
- [x] `src/foundry/skills/open_pr_worktree.py` — read-only echo env-переменных,
  по аналогии с `open_worktree`.
- [x] `src/foundry/automations/registry.py` — `PR_REVIEW` запись.
- [x] `src/foundry/automations/prompts/pr_review.md` — промпт.
- [x] `src/foundry/orchestrator.py` — `_prepare_worktree` теперь возвращает
  `cleanup_fn`, исполняется в `finally`. Пробрасывает в env: `FOUNDRY_PR_REPO`,
  `FOUNDRY_PR_HEAD_SHA`, `FOUNDRY_PR_NUMBER`, `FOUNDRY_PR_URL`,
  `FOUNDRY_PR_AUTHOR`, `PR_REVIEW_BASE_PATH`. (Prior-run summary не нужен —
  CLI session resume по `session_id` даёт агенту полный контекст прошлого review.)
- [x] `src/foundry/config.py` — `pr_review_base_path: Path | None`, парсит
  `PR_REVIEW_BASE_PATH`.
- [x] `.env.example` — секция `# PR review automation (optional)`.
- [x] Тесты:
  - [x] `tests/test_pr_worktree.py` — slug-нормализация, discovery, prepare/cleanup.
  - [x] `tests/test_skill_open_pr_worktree.py` — env-валидация.
  - [x] `tests/test_orchestrator_pr_review.py` — `session_key` склеивание,
    `pr_worktree` путь + cleanup, FAILED/infra при отсутствии base_path.
  - [x] `tests/test_automations_registry.py` — расширен на `pr_review`.

## Решения по открытым вопросам

- **Force-push после emit'а** (`head_sha` пропал на GitHub): оставлено как есть —
  `git fetch origin <sha>` падает, `prepare_pr_worktree` бросает `ShellError`,
  оркестратор маркирует run `FAILED + infra`. Если head съехал — это «прошлогодний
  снег», новый push прилетит свежим event'ом.
- **Cleanup при `stop` через UI**: текущий `/api/runs/{id}/stop` пишет статус в DB,
  но не убивает агентский subprocess. Кода в этом изменении не добавлял — `finally`
  в `execute_run` срабатывает только когда субпроцесс завершится. Это проблема
  всего lifecycle, не специфика PR-review; решать отдельно.
- **`run_tests` в allowlist**: не добавил. v1 — read-only review.
