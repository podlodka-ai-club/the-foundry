# DEBUG.md

Verified runbook for autonomous work in this repo. **Every technique below was executed and its output observed** before being documented here. Environment: macOS (darwin), Python 3.13.2 in `.venv`, `uv 0.6.12`, `gh 2.71.2`.

The repo has exactly **one process runtime**: the `foundry` Python CLI (`src/foundry`, entrypoint `foundry = "foundry.cli:main"`). External tools invoked as subprocesses: `gh` (GitHub CLI) and `git`. State lives in SQLite at `$DB_PATH`.

---

## Runtime: `foundry` CLI (Python 3.11+)

### Environment setup (verified)

```bash
uv sync
```
Output: `Resolved 10 packages ... Audited 9 packages`. Creates `.venv/` and installs editable `foundry` package.

### Start / invoke (verified)

```bash
uv run foundry --help
uv run foundry status
uv run foundry reset <task_id>
uv run foundry run
```
Observed: `foundry --help` lists `reset | run | status`. No long-running daemon — `run` is one pass and exits. No "stop" step.

### Required env for any command that loads `Settings` (verified)

`SOURCE_REPO` and `TARGET_REPO` are required; missing them aborts with exit 2:
```bash
$ uv run foundry status
config error: SOURCE_REPO and TARGET_REPO must be set (owner/name)
exit=2
```
Override `DB_PATH` to isolate from the shared `./data/foundry.sqlite`:
```bash
SOURCE_REPO=demo/x TARGET_REPO=demo/x DB_PATH=/tmp/foundry-probe.sqlite uv run foundry status
```

### Logging (verified)

`structlog` with `ConsoleRenderer` is wired in `foundry.cli._configure_logging`. Logs go to **stdout** with ANSI colors. Probe:
```bash
uv run python -c "
from foundry.cli import _configure_logging
import structlog
_configure_logging()
structlog.get_logger().info('debug.probe', value=42)
"
# → 2026-04-23T14:21:25Z info     debug.probe  value=42
```
Inside the pipeline, events are `run.fetched`, `task.start`, `task.done`, `task.requeued`, `task.failed` (see [src/foundry/pipeline.py](src/foundry/pipeline.py)). No file sink — redirect stdout if you need a log file: `uv run foundry run > /tmp/run.log 2>&1`.

### Eval / REPL (verified — this is the primary fast-feedback loop)

There is no debug server. Use `uv run python -c '...'` as the eval mechanism — it imports the live source tree (editable install), so every call sees current code without a rebuild.

**State driving** (seed the DB without hitting GitHub):
```bash
uv run python -c "
from pathlib import Path
from foundry import state
from foundry.models import Task
db = Path('/tmp/foundry-probe.sqlite')
state.init_db(db)
t = state.upsert_task(db, Task(repo='demo/x', issue_number=1, issue_title='probe', issue_body=''))
print('inserted id=', t.id)
"
# → inserted id= 1
```
Then inspect via CLI:
```bash
SOURCE_REPO=demo/x TARGET_REPO=demo/x DB_PATH=/tmp/foundry-probe.sqlite uv run foundry status
#  id   issue  status    stage       pr
#   1       1  pending   fetch       -
```

**Shell wrapper smoke-check:**
```bash
uv run python -c "
from foundry import shell
print(shell.run(['echo', 'hi']).stdout)
try: shell.run(['false'])
except shell.ShellError as e: print('raised rc=', e.returncode)
"
# → hi
# → raised rc= 1
```

**`gh` reachability from inside the wrapper:**
```bash
uv run python -c "
import json; from foundry import shell
print(json.loads(shell.run(['gh','api','rate_limit']).stdout)['rate']['remaining'])
"
# → 4987  (observed against live github.com; gh is authenticated as 'arhangel66')
```

### Rebuild / reload (verified)

`uv sync` installs `foundry` as an editable package (`src/foundry/`). **Code changes take effect on the next `uv run` — no rebuild, no restart** (each `uv run foundry …` is a fresh process). Tested by editing a log message and re-invoking `uv run foundry --help` — change reflected immediately.

If you change `pyproject.toml` dependencies, re-run `uv sync`.

### Tests (verified)

```bash
uv run pytest              # full suite: 11 passed in 0.13s
uv run pytest -v           # verbose
uv run pytest tests/test_pipeline.py::test_run_once_happy_path -v   # single test
```
Observed output: `============================== 11 passed in 0.13s ==============================`. Tests are offline — every external call (`gh`, git worktree, stages) is mocked at `foundry.pipeline.<name>_stage.<fn>`.

### Running the real pipeline safely

`foundry run` performs live side effects (clone, branch, commit, push, `gh pr create`, `gh issue close`). Before running it:
1. Use a throwaway sandbox repo for both `SOURCE_REPO` and `TARGET_REPO` (they can be the same).
2. Point `WORKTREE_ROOT` at a temp dir; `DB_PATH` at a throwaway sqlite file.
3. `gh auth status` must show a logged-in account (verified: `gh auth status` → `✓ Logged in to github.com account arhangel66`).

---

## Workflows (verified)

`pipeline.run_once` fetches labeled issues as a batch and dispatches each task
through a named workflow from [src/foundry/workflows.py](src/foundry/workflows.py).
Two workflows exist today:

- `dev_task` — full issue cycle: `context → plan → (implement → verify) × N → pr`.
  The `implement → verify` loop runs up to `settings.max_implement_attempts`
  (env `MAX_IMPLEMENT_ATTEMPTS`, default `2`). On retryable verification failure
  the next implement attempt receives the prior verification report in its
  input. `requires_human=True`, non-retryable failures, and exhausted retries
  all stop the loop and mark the task `FAILED`.
- `pr_verify` — verification-only workflow against an existing task + worktree
  context. Calls `verify_stage.run`, records `stage_started`/`stage_finished`
  events with `workflow=pr_verify` in the payload, and returns a
  `VerificationDecision`. Does **not** commit, push, open a PR, close the
  source issue, or mark the task `DONE`.

### Manually exercise `dev_task` in-process (verified)

```bash
SOURCE_REPO=demo/x TARGET_REPO=demo/x DB_PATH=/tmp/foundry-probe.sqlite \
uv run python -c "
from pathlib import Path
from unittest.mock import patch
from foundry import pipeline, state
from foundry.config import Settings
from foundry.models import Task

db = Path('/tmp/foundry-probe.sqlite')
state.init_db(db)
seed = state.upsert_task(db, Task(repo='demo/x', issue_number=1, issue_title='probe', issue_body=''))
settings = Settings(
    source_repo='demo/x', target_repo='demo/x', issue_label='agent-task',
    worktree_root=Path('/tmp/foundry-wt'), db_path=db, poll_interval_seconds=30,
    max_implement_attempts=2,
)
with patch('foundry.pipeline.fetch_stage.fetch', return_value=[seed]), \
     patch('foundry.workflows.worktree.ensure_base_repo', return_value=Path('/tmp/base')), \
     patch('foundry.workflows.worktree.create_worktree', return_value=(Path('/tmp/wt'), 'br')), \
     patch('foundry.workflows.worktree.cleanup_worktree'), \
     patch('foundry.workflows.agent_plan_stage.run', return_value={'plan':'p','summary':''}), \
     patch('foundry.workflows.agent_implement_stage.run', return_value={'result':'', 'response':''}), \
     patch('foundry.workflows.verify_stage.run', return_value={'passed': True}), \
     patch('foundry.workflows.pr_stage.run', return_value={'pr_url':'x','branch':'br'}):
    print([t.status for t in pipeline.run_once(settings)])
"
# → [<TaskStatus.DONE: 'done'>]
```

### Manually exercise `pr_verify` (verified)

```bash
DB_PATH=/tmp/foundry-probe.sqlite uv run python -c "
from pathlib import Path
from unittest.mock import patch
from foundry import state, workflows
from foundry.config import Settings
from foundry.models import Task

db = Path('/tmp/foundry-probe.sqlite')
state.init_db(db)
task = state.upsert_task(db, Task(repo='demo/x', issue_number=2, issue_title='verify-only', issue_body=''))
settings = Settings(
    source_repo='demo/x', target_repo='demo/x', issue_label='agent-task',
    worktree_root=Path('/tmp/foundry-wt'), db_path=db, poll_interval_seconds=30,
)
with patch('foundry.workflows.verify_stage.run', return_value={'passed': True, 'report': 'green'}):
    d = workflows.pr_verify(settings, task, Path('/tmp/wt'))
print('passed=', d.passed, 'report=', d.report)
"
# → passed= True report= green
```

---

## Known limitations

- **No process supervisor / daemon** — `foundry run` is a single pass. To iterate, just re-invoke the command.
- **No built-in debug HTTP endpoint** — not needed: `uv run python -c …` gives direct access to the same process space the CLI uses.
- **No hot reload mechanism** — and none needed, since each CLI call is a fresh Python process over the editable source.
- **GitHub auth is implicit** — handled by `gh` CLI, not by `GITHUB_TOKEN` in `.env`. The env var is currently unused (see [config.py](src/foundry/config.py)).
- **Tests don't hit GitHub** — they mock stage functions at the `foundry.pipeline` import path, not at the source module. If you add a new stage, mock it via `foundry.pipeline.<stage>_stage.run`.
