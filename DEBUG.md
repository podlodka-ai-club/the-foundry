# DEBUG.md

Verified runbook for autonomous work in this repo. **Every command and snippet below was executed and its output observed** before being documented here. All probes ran on macOS (Darwin 25.x) with `uv 0.6.x`, Python 3.13.2 in `.venv`, Node 24.9, `gh 2.71.x`, `claude 2.1.126`, `codex 0.113`, `opencode 1.14.25`.

## Runtimes in this repo

The Foundry has **three concurrent runtimes** plus three external coding-agent CLIs (spawned on-demand per run):

| # | Runtime | Process | Source | Default port |
|---|---------|---------|--------|--------------|
| 1 | `foundry serve` (orchestrator + listeners) | `python` long-lived asyncio loop | `src/foundry/cli.py` | — (writes to SQLite) |
| 2 | FastAPI HTTP API (web UI backend) | `uvicorn` | `src/api/main.py` | 8000 |
| 3 | Vite + React dev server (web UI) | `vite` (node) | `web/` | 5173 |
| 4 | Per-run MCP server | `python -m foundry.mcp.server` (stdio) | `src/foundry/mcp/server.py` | — (subprocess of agent CLI) |
| 5 | Coding agent CLI | `claude` / `codex` / `opencode` (or `stub`) | spawned by orchestrator | — |

All inter-runtime communication is via **SQLite** at `${DB_PATH}` (default `./data/foundry.sqlite`). The orchestrator and API are separate processes; SSE in the API polls the DB rather than using in-process pubsub.

---

## Runtime 1 — `foundry serve` (orchestrator + listeners)

### Environment setup (verified)

```bash
uv sync
# Resolved 97 packages in 0.76ms
# Audited 91 packages in 0.13ms
```

### CLI surface (verified)

```bash
uv run foundry --help
# Commands: runs | serve
uv run foundry runs --help
# Options: --status TEXT (running/waiting/done/failed/unclear) --limit INT
```

### Required env (verified)

`SOURCE_REPO` and `TARGET_REPO` must be set or `load_settings()` raises `ConfigError` (exit 2). All other settings have defaults. Override `DB_PATH` and `WORKTREE_ROOT` to isolate from the live `./data/foundry.sqlite`:

```bash
SOURCE_REPO=demo/x TARGET_REPO=demo/x \
  DB_PATH=/tmp/foundry-probe.sqlite \
  WORKTREE_ROOT=/tmp/foundry-probe-wt \
  uv run foundry runs
# no runs yet  (when DB is fresh)
```

### Start / stop (verified)

`foundry serve` runs all listeners + orchestrator until SIGINT/SIGTERM. **Important:** `uv run` is a wrapper; signals must be sent to the python child, not to `uv` itself.

```bash
SOURCE_REPO=demo/x TARGET_REPO=demo/x \
  DB_PATH=/tmp/foundry-serve-probe.sqlite \
  WORKTREE_ROOT=/tmp/foundry-serve-wt \
  LISTENERS_ENABLED=discord \
  uv run foundry serve > /tmp/foundry-serve.log 2>&1 &
PID=$!
sleep 2
CHILD=$(pgrep -P $PID)        # python child
kill -INT $CHILD              # NOT $PID
```

Observed log (ANSI stripped):
```
serve.start                    listener_ids=['discord']
listener.start                 listener=discord
listener.discord.stub_started
serve.stopping
serve.stopped
```

`LISTENERS_ENABLED` is a comma-separated allowlist of listener ids (`github_issues`, `cron`, `discord`, `telegram`); empty/unset means **all**. The `discord` listener is an idle stub — useful for keeping `serve` alive without external side-effects. The `cron` listener exits cleanly at startup because `DEFAULT_CRON_RULES` is empty (`src/foundry/listeners/cron_rules.py`).

### ⚠ Live `.env` warning

The repo's `.env` enables a real Telegram bot token. Running a second `foundry serve` while the production daemon is running causes Telegram `409 Conflict` (`getUpdates` is single-consumer). Always probe `serve` with explicit env overrides like `LISTENERS_ENABLED=discord` and a `TELEGRAM_BOT_TOKEN=` empty override; never assume the env file is debug-safe.

### Logging (verified)

`structlog` with `ConsoleRenderer` is wired in `foundry.cli._configure_logging`. Logs go to **stdout** with ANSI colors. Probe:

```bash
uv run python -c "
from foundry.cli import _configure_logging
import structlog
_configure_logging()
structlog.get_logger().info('debug.probe', value=42)
"
# 2026-05-02T06:44:00Z [info     ] debug.probe                    value=42
```

For a logfile use redirection. `sed 's/\x1b\[[0-9;]*m//g'` strips ANSI for clean reads.

Event names follow dotted convention (`run.start`, `serve.start`, `listener.crashed`, `orchestrator.handle_event_failed`). Search the codebase via `grep -rn 'log\.\(info\|warning\|exception\)' src/foundry/`.

---

## Runtime 2 — FastAPI HTTP API

### Start (verified)

The API resolves `DB_PATH` lazily through the `get_db_path` dependency. Tests override via `app.dependency_overrides`; **scripts can override via `FOUNDRY_DB_PATH_OVERRIDE` env var** (see [src/api/main.py](src/api/main.py:53)).

```bash
FOUNDRY_DB_PATH_OVERRIDE=/tmp/foundry-api-probe.sqlite \
SOURCE_REPO=demo/x TARGET_REPO=demo/x \
  uv run uvicorn api.main:app --port 8901 --log-level warning &
```

Default port in `web/vite.config.ts` is 8000 (proxy target); for probes, pick a free port. Production live ports already in use on this machine: 8000, 8765 — check with `lsof -i:8000`.

### Endpoints (verified end-to-end)

Seeded a probe DB with one event + one run + one run_event, then hit each endpoint. Output observed:

```
GET /                             → {"status":"ok"}
GET /api/automations              → [ {id:"dev_task", counts:{running:1,waiting:0,pending:0,total:1}}, {id:"tg_chat",…} ]
GET /api/triggers                 → [ {id:"github_issues", health:"stale", last_seen:"…"}, {id:"cron", health:null}, … ]
GET /api/runs                     → [ {id:1, automation_id:"dev_task", status:"running", trigger:{…}} ]
GET /api/runs/1                   → {…, events:[{seq:1, stage:"run", kind:"stage_started", payload:{…}}] }
POST /api/runs/N/messages         → body {"type":"reply"|"continue"|"enqueue", "text":"..."}; returns {"ok":true,"seq":N}
POST /api/runs/N/stop             → {"ok":true}; second call returns 409 "already in terminal status failed"
POST /api/runs/N/retry            → {"ok":true,"run_id":<new>}; only works on terminal runs
```

Body for `/messages` requires `type` (literal `continue|enqueue|reply`) **and** `text`. Missing `type` returns 422. Verified.

### Server-Sent Events (verified)

```bash
curl -s -N -m 2 http://127.0.0.1:8901/api/runs/1/events
# id: 1
# event: run_event
# data: {"seq": 1, "run_id": 1, "stage": "run", "kind": "stage_started", "ts_ms": 1777704372187, "payload": {"phase": "kickoff"}, "parent_event_seq": null}
```

Frame format is `id:` / `event: run_event` / `data:` JSON. Honours `Last-Event-ID` for resume. Implementation polls SQLite via `bus.subscribe(...)` (default 0.5 s; override per-call or via `FOUNDRY_SSE_POLL_SEC`).

### Stop (verified)

`uv run uvicorn` again is a `uv` wrapper around python — kill the **child**:

```bash
kill -TERM $(pgrep -P $UV_PID)
```

### Eval / REPL into the API runtime

The API has no in-process eval endpoint. To inspect server-side behaviour, drive the same code path via `uv run python -c …` (each `uv run` re-imports the live source tree, no rebuild needed). To override the DB during probes, set `FOUNDRY_DB_PATH_OVERRIDE` before importing FastAPI route handlers.

---

## Runtime 3 — Vite + React dev server

### Setup (verified)

```bash
cd web && npm install
ls node_modules/.bin/vite   # /Users/.../web/node_modules/.bin/vite
```

### Start (verified)

```bash
cd web && npm run dev -- --port 5174 > /tmp/foundry-vite.log 2>&1 &
```

Observed log:
```
> web@0.0.0 dev
> vite --port 5174
  VITE v8.0.10  ready in 205 ms
  ➜  Local:   http://localhost:5174/
```

### HTTP probe (verified)

```bash
curl -s -o /tmp/vite-root.html -w "http=%{http_code} size=%{size_download} ct=%{content_type}\n" http://localhost:5174/
# http=200 size=631 ct=text/html
head -5 /tmp/vite-root.html   # <!doctype html>... <script type="module">...
curl -s -o /dev/null -w "ct=%{content_type}\n" http://localhost:5174/src/main.tsx
# ct=text/javascript                # — Vite serves TS modules transformed
```

⚠ Bind on `localhost`, not `127.0.0.1` — `curl http://127.0.0.1:5174/` returned `http=000` (Vite v8 binds IPv6 by default).

### Proxy /api → FastAPI (verified)

`web/vite.config.ts` proxies `/api` to `http://localhost:8000`. With the API up on :8000:

```bash
curl -s http://localhost:5174/api/automations | head -c 300
# [{"id":"dev_task","name":"GitHub issue → PR",…}]
```

### Stop (verified)

```bash
pkill -TERM -P $NPM_PID    # kills node child + vite worker
```

### Hot reload

Verified by serving `main.tsx` after edit (`http=200 ct=text/javascript`). Vite's HMR is the default reload mechanism for the React UI; no special command needed. For TypeScript-strict checking outside of dev mode: `cd web && npm run build`.

### Browser-side eval

No bespoke debug server exists. Use the browser DevTools console for runtime introspection of React-Query cache (`window.__REACT_QUERY_DEVTOOLS__` is not enabled). For headless verification of API contract, prefer driving the FastAPI directly via `curl`.

---

## Runtime 4 — Per-run MCP server (FastMCP, stdio)

The orchestrator writes a per-run MCP config (`worktrees/run-<N>-mcp.json`) and the agent CLI spawns the server as a stdio subprocess. The server reads `FOUNDRY_DB_PATH`, `FOUNDRY_RUN_ID`, and optional `FOUNDRY_PARENT_EVENT_SEQ` from env. There is no per-run skill whitelist — `SKILL_REGISTRY` is registered unconditionally (currently `commit_and_push_pr`, `telegram_reply`, `wait_for_human`) plus `call_subagent`.

Run-level signalling (`mark_done` / `mark_failed`) is **not** an MCP tool anymore — the orchestrator parses a `STATUS:` marker out of the agent's final reply (see `foundry.status_marker`).

### Build a config (verified)

```python
uv run python -c "
from pathlib import Path
from foundry.mcp.config import build_mcp_config, write_mcp_config, mcp_config_path_for_run
cfg = build_mcp_config(
    db_path=Path('/tmp/x.sqlite'), run_id=42, automation_id='dev_task',
    extra_env={'FOUNDRY_WORKTREE':'/tmp/wt-42'},
)
p = mcp_config_path_for_run(Path('/tmp/foundry-wt'), 42)
write_mcp_config(p, cfg); print(p, p.read_text()[:120])
"
```

### Probe the tool surface in-process (fastest loop)

```bash
uv run python -c "
from foundry.mcp.server import _REGISTERED
print('skills:', sorted(_REGISTERED))
"
# skills: ['commit_and_push_pr', 'telegram_reply', 'wait_for_human']
```

### Probe STATUS-marker parsing (replaces mark_done debug)

```bash
uv run python -c "
from foundry.status_marker import parse_status_marker
print(parse_status_marker('all green\n\nSTATUS: done'))
print(parse_status_marker('STATUS: approved'))
print(parse_status_marker('STATUS: change_requested'))
print(parse_status_marker('STATUS: failed:acceptance'))
print(parse_status_marker('no marker here'))
"
# (<RunStatus.DONE: 'done'>, None, None)
# (<RunStatus.DONE: 'done'>, None, 'approved')
# (<RunStatus.DONE: 'done'>, None, 'change_requested')
# (<RunStatus.FAILED: 'failed'>, <FailureKind.ACCEPTANCE: 'acceptance'>, None)
# None
```

The 3rd element is the semantic `outcome` (whitelist: `approved` /
`change_requested` / `rejected`) — DONE-lifecycle but coloured pill in UI.

---

## Runtime 5 — Coding-agent CLIs

Backends and their binaries (all installed locally — verified):

| Backend         | CLI       | Version (probe) |
|-----------------|-----------|-----------------|
| `stub`          | none — pure Python, offline | n/a |
| `claude_cli`    | `claude`  | 2.1.126 |
| `codex_cli`     | `codex`   | 0.113.0 |
| `opencode_cli`  | `opencode`| 1.14.25 |

### Factory smoke (verified — no LLM call)

```bash
uv run python -c "
from foundry.agents.factory import make_agent
from foundry.agents.config import AgentSettings
from foundry.agents.base import AgentStage
for b in ('stub','claude_cli','codex_cli','opencode_cli'):
    a = make_agent(AgentSettings(stage=AgentStage.IMPLEMENT, backend=b, model='haiku', db_path=None))
    print(f'{b:12} -> {type(a).__name__}')
"
# stub         -> StubAgent
# claude_cli   -> ClaudeCliAgent
# codex_cli    -> CodexCliAgent
# opencode_cli -> OpencodeCliAgent
```

### Offline end-to-end via `stub` (verified)

```bash
uv run python -c "
from pathlib import Path
import tempfile
from foundry.agents.factory import make_agent
from foundry.agents.config import AgentSettings
from foundry.agents.base import AgentStage, AgentTask
with tempfile.TemporaryDirectory() as tmp:
    wt = Path(tmp); (wt/'README.md').write_text('seed\n')
    agent = make_agent(AgentSettings(stage=AgentStage.IMPLEMENT, backend='stub', model='haiku', db_path=None))
    res = agent.apply(task=AgentTask(id=None, title='hello', description=''), worktree=wt, input='go')
    print('summary:', res.result)
    print('readme:', (wt/'README.md').read_text())
"
# summary: appended 1 line to README.md (32 bytes) for issue #None
# readme: seed
# foundry-bot: task #None — hello
```

`StubAgent.apply()` writes a line to `README.md` for `IMPLEMENT`, returns trivial text for `PLAN`/`VERIFY`. Use it whenever you want to exercise the orchestrator path end-to-end without burning model credits.

### Spawning the real CLI

`ClaudeCliAgent` shells out via `claude -p <prompt> --output-format stream-json --verbose --dangerously-skip-permissions --max-turns N --model M --mcp-config <run-cfg.json>`. **Do not** trigger this from a probe unless you intend to spend credits — use `stub` for plumbing tests.

### Auth (per backend)

- **claude_cli** — `claude /login` (subscription OAuth) **or** `ANTHROPIC_API_KEY`. Verified locally: `claude --version` works without re-auth.
- **codex_cli** — `codex login` (ChatGPT Plus/Pro) or `OPENAI_API_KEY`.
- **opencode_cli** — provider keys read from `~/.local/share/opencode/auth.json` (e.g. `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`).

---

## State driving (verified — the canonical fast-feedback recipes)

### Init a fresh isolated DB

```bash
uv run python -c "
from pathlib import Path
from foundry import state
db = Path('/tmp/foundry-probe.sqlite'); db.unlink(missing_ok=True)
state.init_db(db)
import sqlite3
print(sorted(r[0] for r in sqlite3.connect(db).execute('select name from sqlite_master where type=\"table\"')))
"
# ['events', 'run_events', 'runs', 'sqlite_sequence']
```

`init_db` drops the legacy `tasks`, `task_events`, and `orchestrator_state` tables, then runs lightweight `ALTER TABLE` migrations for new columns (`runs.agent_session_id`, `events.trigger_id`).

### Seed an event + a run + a run_event (verified)

```bash
uv run python -c "
from pathlib import Path
from foundry import state, events
from foundry.models import RunStatus
db = Path('/tmp/foundry-probe.sqlite')
state.init_db(db)
from unittest.mock import patch
with patch('foundry.events.automations_for_trigger', return_value=[]):
    ev_id = events.dispatch_event(db, trigger_id='github_issues.issue_opened', dedupe_key='r/r#1',
        payload={'number':1,'title':'probe','body':'','repo':'r/r','labels':['agent-task']})
run_id = state.create_run(db, automation_id='dev_task', event_id=ev_id,
    session_id='sess-probe', session_seq=1, status=RunStatus.RUNNING)
events.record_event(db, run_id=run_id, stage='run', kind='stage_started', payload={'phase':'kickoff'})
print('event=', ev_id, 'run=', run_id)
"
# event= 1 run= 1
```

Note: in production code listeners call `dispatch_event` directly (no patch), and it materializes a `PENDING` run for every subscribed automation in the same transaction. The patch above isolates the seed step from real automation subscriptions when probing.

### `stage_span` paired events (verified)

```bash
uv run python -c "
from pathlib import Path
from foundry import state, events
from foundry.models import RunStatus
db = Path('/tmp/foundry-events-probe.sqlite'); db.unlink(missing_ok=True)
state.init_db(db)
from unittest.mock import patch
with patch('foundry.events.automations_for_trigger', return_value=[]):
    ev = events.dispatch_event(db, trigger_id='cron.noop', dedupe_key='ev-1', payload={'rule_id':'noop'})
run_id = state.create_run(db, automation_id='dev_task', event_id=ev, session_id='S', session_seq=1, status=RunStatus.RUNNING)
with events.stage_span(db, run_id=run_id, stage='probe'):
    events.record_event(db, run_id=run_id, stage='probe', kind='note', payload={'msg':'hello'})
import sqlite3
for row in sqlite3.connect(db).execute('select seq,stage,kind,payload from run_events'):
    print(row)
"
# (1, 'probe', 'stage_started', '{}')
# (2, 'probe', 'note', '{\"msg\": \"hello\"}')
# (3, 'probe', 'stage_finished', '{\"duration_ms\": 0}')
```

### Inspect via CLI

```bash
SOURCE_REPO=demo/x TARGET_REPO=demo/x DB_PATH=/tmp/foundry-probe.sqlite \
  uv run foundry runs --status running --limit 5
```

### Shell wrapper smoke (verified)

```bash
uv run python -c "
from foundry import shell
print(repr(shell.run(['echo','hi']).stdout.strip()))
try: shell.run(['false'])
except shell.ShellError as e: print('rc=', e.returncode)
"
# 'hi'
# rc= 1
```

### `gh` reachability (verified)

```bash
uv run python -c "
import json; from foundry import shell
print('rate.remaining=', json.loads(shell.run(['gh','api','rate_limit']).stdout)['rate']['remaining'])
"
# rate.remaining= 4996
```

---

## Tests (verified)

```bash
# CWD must be the project root — testpaths = ["tests"] is relative.
cd /Users/mikhail/w/learning/the-foundry
uv run pytest                            # 258 passed in 4.97s
uv run pytest tests/test_api.py -v       # 18 passed in 0.41s
uv run pytest tests/test_api_sse.py tests/test_bus.py
uv run pytest -k "mcp"                   # subset
```

Pytest config: `pyproject.toml` → `pythonpath = ["src"]`, `asyncio_mode = "auto"`. Tests don't hit GitHub or spawn agent subprocesses — every external is mocked. SSE tests drive `bus.subscribe(...)` directly with `poll_interval=0.05` (fast and deterministic) instead of going over HTTP.

---

## Rebuild / hot reload

| Runtime | Reload model |
|---------|--------------|
| `foundry serve`, `uv run foundry …` | Editable install — every `uv run` is a fresh python process over live source. No rebuild step. |
| `uvicorn api.main:app` | Add `--reload` for autorestart on file change. |
| Vite | HMR by default. `npm run build` for prod bundle (does `tsc -b && vite build`). |
| MCP server (per-run) | Spawned fresh by the agent on each new run; no need to "reload". |
| Coding-agent CLI | External binary; `brew upgrade --cask claude` etc. |

If `pyproject.toml` deps change, re-run `uv sync`.

---

## Observability primer

- **`run_events`** is the canonical write-once event log per run (UI source of truth). Use `events.record_event(db, run_id, stage, kind, payload)` — assigns `seq` atomically with retry on `IntegrityError`.
- **`stage_span(db, run_id, stage)`** context manager emits paired `stage_started` / `stage_finished` / `stage_failed` with duration.
- Streaming CLI events go through `agents/streaming.py::_normalize_tool_event` — reuse it for any new CLI-backed agent rather than rolling a second shape.
- For Langfuse tracing, set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` in `.env` (no error if missing — disabled gracefully).

---

## Known limitations / gotchas

- **`uv run` swallows signals.** SIGINT to `uv run …` does **not** propagate to the python child cleanly. Use `pgrep -P $UV_PID` to find the child and signal it directly.
- **Vite v8 + IPv6.** `curl http://127.0.0.1:5173/` returns no response; use `http://localhost:5173/`.
- **Live `.env` is not safe for probes.** It enables a real Telegram bot; running a second `foundry serve` causes a Telegram `409 Conflict` on `getUpdates`. Always set `LISTENERS_ENABLED=` (subset) and empty out `TELEGRAM_BOT_TOKEN=` for probes.
- **`pytest` with no path runs from CWD.** `cd` to the project root or pass an explicit path; running from `web/` returns "no tests ran" silently.
- **`/api/runs/{id}/messages` body** requires both `type` (`continue|enqueue|reply`) **and** `text`. Missing `type` returns 422.
- **Production processes may already be running.** Check `pgrep -af "foundry serve|uvicorn api"` before starting probes; share-DB conflicts otherwise.
- **No coding-agent probe should be run blindly.** `ClaudeCliAgent`/`CodexCliAgent`/`OpencodeCliAgent` shell out to a real LLM and cost money. Use the `stub` backend for orchestrator/skill plumbing tests.
