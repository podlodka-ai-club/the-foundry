## Context

The Foundry pipeline (`src/foundry/pipeline.py`) runs `fetch → context → plan → implement → verify → pr → done`. Three reasoning stages are LLM-free stubs (`plan` hardcodes `append_line`, `implement` applies it, `verify` runs `echo ok`) plus a `context` stub returning `{"files": []}`. Real `fetch` (via `gh`) and real `pr` (commit/push/`gh pr create`) already work. Each task gets an isolated git worktree (`worktree.py`); state lives in SQLite (`state.py`); external tools go through `shell.run` (`shell.py`). A long-form exploration doc sits at `docs/architecture/agent-protocol.md`.

This change is a **preparatory, strictly additive** step: we ship a standalone `src/foundry/agents/` package that a future change will wire into the pipeline. Nothing in the existing code is touched. The scope is narrow on purpose — getting the Protocol and backend adapters right is easier to review in isolation, and lets us dogfood the adapters via a scratch script before anyone depends on them.

Stakeholders: single developer (Mikhail), sole operator and reviewer. No external consumers; internal contracts can change cheaply later.

Constraints:
- Python 3.11+, `from __future__ import annotations`, PEP-604 unions, frozen dataclasses for DTOs.
- Subprocess-only — no new Python deps.
- Must run `uv run pytest` green without any external CLI installed (so `stub` is the only backend exercised by default).

## Goals / Non-Goals

**Goals:**
- Ship a `CodingAgent` protocol with four backends (`stub`, `claude_cli`, `opencode`, `codex_cli`) as a self-contained package.
- Keep the contract minimal: strings in, strings out, three stages, no session plumbing leaked to callers.
- Hide backend-specific session-resume mechanics (`--resume` / `--session` / `resume <id>`) behind private per-adapter state so a future caller can repeat-call `apply(stage=PLAN, …)` and get a coherent conversation without knowing anything about session ids.
- Land unit tests per backend using mocked `subprocess.run` so CI runs offline.
- Include a short `README.md` in the package showing a scratch-script usage example — enough that the next change knows how to wire it.

**Non-Goals:**
- Wiring the agents into any stage. `plan`/`implement`/`verify` stubs keep running unchanged.
- Prompt templates under `src/foundry/stages/prompts/`. Prompts belong to stages, and stages are not being modified.
- Pipeline FSM changes, new `Task` fields, new statuses, SQLite migrations.
- Human-in-the-loop clarification flow (the `NEED_VERIFICATION` marker convention is documented in the follow-up change, not here).
- Retry loop, cost/turn budget gates, streaming output, Langfuse-style observability.
- Cross-process session persistence. In-memory only; process restart loses it.
- Aider backend.
- Tuning the prompts themselves — that happens when stages start rendering them.

## Decisions

### 1. Single `CodingAgent.apply(task, worktree, stage, input) -> AgentResult` method

One method parameterized by `AgentStage`, not three per-stage methods and not a free-form `run(prompt, **kwargs)`.

**Why**:
- All three stages will share the same adapter skeleton: build command, shell out, parse JSONL/JSON output, extract final-assistant text, return dataclass. Per-stage methods would copy that four times per backend.
- Adding a fourth logical agent later is a new enum value plus any per-stage behavior — no interface churn.
- `stage` is the only thing that varies in how the adapter picks max-turns and session-resume behavior, so it earns its place as a named parameter instead of hiding in a dict.

**Alternatives considered**:
- Per-stage methods — more typed, but the save doesn't pay for the duplication.
- `run(prompt, **kwargs)` — pushes prompt assembly back to callers and erases the stage signal the adapter uses to pick `max_turns` + session state. Rejected.

### 2. Strings in, strings out — no structured payloads in `AgentResult`

`AgentResult` is `(stage, response, result)`. Both fields are `str`. No `success: bool`, no `changed_files: list[str]`, no `session_id`, no tokens/cost, no `raw_events`.

**Why**:
- First-line protocol ("response starts with a one-line summary") covers `result` for all three stages: `PLAN` gets a plan headline; `IMPLEMENT` gets a change headline; `VERIFY` gets `PASS` or `FAIL: <reason>`. The prompt tells the agent to do this; the adapter just extracts `response.splitlines()[0][:200]`.
- Success is caller-dependent: `IMPLEMENT` success = non-empty `git status --porcelain`; `VERIFY` success = `result.startswith("PASS")`. The agent can't know which rule applies, so putting `success: bool` into the dataclass forces each adapter to decide — and they'd decide inconsistently. Defer to caller.
- Token counts and cost are useful for budgeting but nothing in scope consumes them. Raw stdout still lands in `logs_json` via the future stage wiring, so debugging isn't blocked.
- `session_id` is ruled out by Decision 3.

**Alternatives considered**:
- `data: dict` — we flirted with it for `changed_files`/`passed`/etc. Rejected because each stage needs a different shape; a shared dict bag hides those shapes. Ground-truthing from git at the call site is simpler.
- Separate per-stage result classes (`PlanResult`, `ImplementResult`, …) — future work if the contract outgrows strings. Not today.

### 3. Session state is **private state of the adapter instance**, not part of the contract

Factory: `make_agent(agent_settings: AgentSettings, task_id: int) -> CodingAgent`. Each real adapter holds `self._cli_sessions: dict[AgentStage, str]`. First `apply(stage=X)` runs fresh; the adapter extracts the CLI-native session id from the JSONL stream and stores it under `X`. Second `apply(stage=X)` looks it up and passes `--resume <id>` (or the backend's equivalent). `stub` stores nothing. The pipeline never sees a session id.

**Why**:
- The intended usage pattern (same logical agent called repeatedly within a stage, e.g. for a future clarification loop) works without leaking id mechanics to callers.
- Keeps `AgentResult` minimal.
- Matches how the three CLI tools actually work — each generates its own id and expects it back in its own flag — so there's no per-backend session-id conversion code in pipeline glue.
- Process restart clears the dict, so a crashed task starts fresh next run. Acceptable for MVP; not planning to pay for persistence yet.

**Alternatives considered**:
- Round-trip via `AgentResult.session_id` + `apply(..., session_id=...)` — works, but leaks the concept to every caller and forces a new `Task.session_id` column. Rejected with scope.
- Persist the dict to disk/SQLite so restarts don't lose sessions — nothing consumes it yet; cross-restart continuity is a separate feature.
- Expose a `reset(stage)` method for forcing-fresh — overkill; just build a new adapter via `make_agent`.

### 4. Per-task adapter instances

`make_agent(agent_settings, task_id)` returns a new `CodingAgent` per `task_id`. Two tasks = two adapters, each with its own `_cli_sessions` dict.

**Why**:
- Session state is keyed by stage, not `(task_id, stage)`; keeping one adapter per task makes that natural.
- Prevents cross-task session confusion (task 42's plan resuming into task 43's implement).
- Trivially swappable: pass a different `AgentSettings` to test alternate backends without globals.

**Alternatives considered**:
- Singleton adapter with `dict[(task_id, AgentStage), str]` — more plumbing for no functional gain.
- Task id baked into the session id to dedupe — unnecessary given per-task instances.

### 5. `AgentSettings` lives in `src/foundry/agents/config.py`, separate from `foundry.config.Settings`

New env vars (`CODING_AGENT`, `AGENT_TIMEOUT_SEC`, `AGENT_MAX_TURNS_*`, `AGENT_MODEL`) are read by a private `AgentSettings` dataclass inside the agents package.

**Why**:
- The pipeline doesn't use these yet — no reason to grow `Settings` prematurely.
- Keeps this change purely additive: zero diff on `foundry.config.py`.
- When the wiring change lands, we can either (a) re-home these onto `Settings` or (b) leave them separate and pass an `AgentSettings` alongside. Decision deferred to that change.

**Alternatives considered**:
- Add fields to `Settings` now — touches an existing file; also costs review attention on a struct that no consumer in this change reads.
- Read env inline inside `make_agent` — no typed dataclass, harder to mock in tests.

### 6. Four backends: `stub`, `claude_cli`, `opencode`, `codex_cli` — all implementing the same Protocol

| Backend       | Fresh call                                                   | Resume call                               |
|---------------|--------------------------------------------------------------|-------------------------------------------|
| `stub`        | in-process Python; `IMPLEMENT` appends a line to `README.md` | ignores stored id (no-op)                 |
| `claude_cli`  | `claude -p <input> --output-format stream-json --verbose --dangerously-skip-permissions --max-turns <n>` | same + `--resume <stored_id>`            |
| `opencode`    | `opencode run <input> --format json`                         | same + `--session <stored_id>`           |
| `codex_cli`   | `codex exec --json <input>`                                  | `codex exec resume <stored_id> --json <input>` (subcommand, not flag) |

The `codex_cli` asymmetry (resume is a subcommand) is handled entirely inside the adapter. From the outside, the three real backends behave identically.

**Why**:
- Each CLI differs enough in auth / provider access that "one real backend" would constrain future model choice.
- They converge cleanly on the Protocol, so the abstraction isn't speculative.

**Alternatives considered**:
- Ship only `claude_cli` first, add others later — fine technically, but the whole point of an abstraction is to validate against multiple real backends before freezing it. Shipping all three now ensures the Protocol actually fits.

### 7. Each adapter parses JSONL and keeps only `response` + CLI session id

JSON mode is mandatory — it's the only reliable way to extract the session id. The adapter reads every event, extracts (a) the final assistant-message text, (b) the session identifier; everything else (tool calls, thinking, progress) is discarded.

**Why**:
- No event history needed: `response` is the full final text; the caller gets exactly what the agent said last.
- `result` is `response.splitlines()[0][:200]` — trivial to compute, no second pass required.
- Keeps adapter code small and resilient to new event types being added by CLI vendors.

**Alternatives considered**:
- Plain-text output — breaks session capture (claude `-p` without `stream-json` omits the session id).
- Preserve full event list for debugging — we already capture raw stdout into `logs_json` in the wiring change. Double-storing is wasteful.

### 8. `stub` does real filesystem work for `IMPLEMENT`; trivial strings for `PLAN`/`VERIFY`

`StubAgent.apply(stage=IMPLEMENT)` does the current `append_line` behavior on the worktree (with the `UnsupportedAction` safety check carried over from the current `stages/implement.py`). `stage=PLAN` returns `response="stub plan for issue N"`, `result="stub plan"`. `stage=VERIFY` returns `response="ok"`, `result="PASS"`.

**Why**:
- Keeps the stub useful: pipeline tests that mock at the agent boundary still exercise a real side-effect on disk for IMPLEMENT.
- Avoids importing `foundry.stages.implement` — the logic moves into the stub and the follow-up wiring change deletes it from the stage module.
- `result="PASS"` makes `verify` pass automatically under `CODING_AGENT=stub`, preserving current CI behavior.

**Alternatives considered**:
- Make stub a pure no-op returning `response=""` for everything — then pipeline tests using the stub would see no actual diff, breaking downstream `pr` stage logic during the follow-up wiring.

### 9. Timeouts are enforced via `subprocess.run(timeout=…)`; exceptions propagate

The adapter calls `subprocess.run(cmd, capture_output=True, text=True, timeout=agent_settings.timeout_sec)`. On `subprocess.TimeoutExpired` or non-zero exit, the adapter re-raises as `ShellError` from `foundry.shell`.

**Why**:
- `shell.ShellError` is the existing convention and `pipeline._process_task`'s try/except treats it consistently.
- Retry policy is the caller's concern — adapter should not retry silently.

**Alternatives considered**:
- Return `AgentResult(response="timeout", result="FAIL: timeout")` instead of raising — hides infra failures as domain failures, exactly the anti-pattern `PRE_IMPLEMENT_STAGES` exists to avoid. Rejected.

## Risks / Trade-offs

- **Session survives only within a process** → if foundry is killed between two `apply()` calls for the same stage, the second call starts fresh. Accepted for MVP because no caller chains calls within a stage yet. Mitigation: the follow-up human-clarification change will either add persistence or live with the loss (a resumed-after-crash clarification simply re-asks the agent from scratch).

- **CLI session id can expire on the provider side** before we try to resume → adapter catches "session not found"-ish `ShellError`, clears its stored id, retries once fresh. To implement as a simple `except ShellError: if 'session' in err.stderr.lower(): retry_fresh(); else: raise`. Documented as a test case.

- **Four backends in one change = four moving targets** → if any single CLI changes its JSON schema, at least one test breaks. Mitigation: fixtures per backend are small (captured once from a real invocation, checked into `tests/fixtures/agents/`); tests stay independent so one backend's breakage doesn't cascade.

- **`codex` may not expose a `--max-turns` equivalent** → adapter simply doesn't pass one and relies on `AGENT_TIMEOUT_SEC` instead. Open question confirms on first live run; worst case we document "codex runs uncapped by turn count, use timeout" and move on.

- **`--dangerously-skip-permissions` for claude CLI is a convention trap** → the agent could in theory run `git push`. The `pr` stage is the designed committer, not the agent; the prompt (shipped in a later change) tells the agent not to commit. Not a hard gate — it's a single-operator dev tool. Accepted.

- **Untyped `str` result contracts rely on prompt discipline** → if the prompt doesn't ask for a first-line summary, `result` becomes whatever random sentence the agent started with. Mitigation: prompts ship in the follow-up change with the conventions baked in; this change's `README.md` documents the expectation so a caller wiring a stage won't be surprised.

- **Drift between backends** → if `claude_cli` gets a bugfix that `opencode` adapter also needs, there's no shared base class forcing parity. Mitigation: common helpers (JSONL line-iter, `first_line()`, `ShellError` re-raise) live in `base.py` (or an internal `_util.py`); each adapter just wires CLI-specific command assembly and parsing on top.

- **Stub doesn't exercise subprocess code paths in tests** → a regression in the subprocess layer could ship unnoticed if only stub runs in CI. Mitigation: the three real-backend tests use `unittest.mock.patch('subprocess.run')` with canned stdout/stderr fixtures — they do exercise the parsing code, just not an actual CLI. A periodic live smoke test (manual, documented in `README.md`) covers the real-CLI path.

## Migration Plan

No deployment, no existing state to evolve. This change is pure addition.

1. Create the `src/foundry/agents/` package with all new files.
2. Add `tests/test_agents_*.py` covering stub (real side-effect on tmp worktree) and the three CLI adapters (mocked `subprocess.run`).
3. Include fixtures in `tests/fixtures/agents/{claude_cli,opencode,codex_cli}/` — small JSONL snippets captured from a single real invocation per backend. Fixtures ship with the change so tests are reproducible.
4. Add `agents/README.md` with a minimal usage example that the follow-up wiring change can literally copy-paste.
5. Ship.

Rollback: delete the package. Nothing else needs to change because nothing else has been touched. Existing `uv run foundry run` behavior is identical before and after this change.

## Open Questions

1. **Does `codex exec` support `--max-turns`?** Unclear from the docs. If not, the adapter ignores `AGENT_MAX_TURNS_*` and falls back to `AGENT_TIMEOUT_SEC`. Confirm on the first live invocation; adjust `README.md` with the answer.
2. **Where do fixtures live long-term?** `tests/fixtures/agents/` is fine for now; if other tests start needing fixtures, we may consolidate into a top-level `tests/fixtures/`. Decide when the second consumer shows up, not before.
3. **Base class vs free functions for shared adapter helpers?** Leaning free functions in `base.py` (JSONL line iter, `first_line`, session-id extraction helpers). No Protocol+ABC mixing. Revisit if the third real adapter repeats a non-trivial pattern that wants inheritance.
4. **Should `AgentTask` include the source repo / issue URL?** Not today — `task.id`, `title`, `description` are enough for the prompts we foresee. If a future stage wants the URL, add it then; the dataclass is frozen so adding a field is a one-line change.
5. **Prompt-location split** — prompts will live under `src/foundry/stages/prompts/` in the follow-up wiring change (per the proposal), not inside the agents package. Revisit if a prompt turns out to be backend-specific rather than stage-specific; in that case it may belong next to the adapter instead.
