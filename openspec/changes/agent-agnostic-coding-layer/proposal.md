## Why

The pipeline's reasoning stages (`plan`, `implement`, `verify`) are LLM-free stubs; the Days 3–4 roadmap replaces them with real LLM work. Before touching the stages, we want a standalone **agent abstraction** in place — a `CodingAgent` protocol and four backends (`stub`, `claude_cli`, `opencode`, `codex_cli`) — that we can build and test in isolation. The existing stub stages keep running as-is until a follow-up change wires them to the new agent. This proposal ships **only** the new `agents/` package and its unit tests; nothing already in the repo is modified.

Reasons to split this out:
- The interface itself is the part where we most want to get decisions right (strings in / strings out, session state encapsulated, three logical agents keyed by stage). Reviewing it apart from the pipeline rewrite keeps the discussion focused.
- We can land, test and dogfood the adapters in a scratch script well before touching the FSM.
- `claude`, `opencode`, `codex` all support headless run + JSON event stream + per-session resume, so the abstraction is concrete rather than speculative. `StubAgent` covers the offline / CI path.

## What Changes

- Add a new package `src/foundry/agents/` (no existing file edited):

  ```
  src/foundry/agents/
      __init__.py           # re-exports AgentStage, AgentTask, AgentResult, CodingAgent, make_agent
      base.py               # Protocol + dataclasses
      config.py             # AgentSettings (env-backed), kept separate from foundry.config.Settings
      factory.py            # make_agent(agent_settings, task_id) -> CodingAgent
      stub.py               # offline, no external deps
      claude_cli.py         # `claude -p ... --output-format stream-json ...`
      opencode_cli.py       # `opencode run ... --format json`
      codex_cli.py          # `codex exec --json ...` / `codex exec resume <id> --json ...`
      README.md             # how a future caller should use the package
  ```

- Minimal, string-based contract:

  ```python
  # src/foundry/agents/base.py
  from enum import StrEnum
  from dataclasses import dataclass
  from pathlib import Path
  from typing import Protocol

  class AgentStage(StrEnum):
      PLAN      = "plan"
      IMPLEMENT = "implement"
      VERIFY    = "verify"

  @dataclass(frozen=True)
  class AgentTask:
      id: int
      title: str
      description: str

  @dataclass(frozen=True)
  class AgentResult:
      stage: AgentStage
      response: str            # full final text the agent produced
      result: str              # first line of response (≤ 200 chars), for logs / routing

  class CodingAgent(Protocol):
      name: str
      def apply(
          self,
          task: AgentTask,
          worktree: Path,
          stage: AgentStage,
          input: str,          # fully composed prompt, caller does the substitution
      ) -> AgentResult: ...
  ```

  Deliberately **not** in the contract (v1): `session_id`, `success`, `changed_files`, `cost_usd`, `tokens_*`, `raw_events`, `params: dict`. Session handling is private state of the agent instance.

- **Per-task agent instances, private session state.** Factory: `make_agent(agent_settings: AgentSettings, task_id: int) -> CodingAgent`. Each real adapter holds an in-memory `dict[AgentStage, str]` mapping stage → CLI-native session id captured from the first call for that stage. The second call for the same stage resumes via `--resume` / `--session` / `resume <id>`. In-memory only — a process restart loses it, which is fine because nothing consumes it yet.

- **Four backends**, all satisfying the same Protocol:
  - `StubAgent` — no external deps. `PLAN`/`VERIFY` return trivial fixtures (`response="stub plan"`, `result="PASS"`, etc.). `IMPLEMENT` is a simple `append_line` side-effect in the worktree so unit tests have a real change to observe.
  - `ClaudeCliAgent` — `claude -p <input> --output-format stream-json --verbose --dangerously-skip-permissions --max-turns <n>` (+ `--resume <stored_id>` on the second call for a stage). Parses JSONL; keeps the final assistant text and the session id; discards everything else.
  - `OpencodeCliAgent` — `opencode run <input> --format json` (+ `--session <stored_id>` on resume).
  - `CodexCliAgent` — `codex exec --json <input>` for fresh, `codex exec resume <stored_id> --json <input>` for resume. Resume is a subcommand rather than a flag; the adapter hides that.

- **Prompts are NOT shipped in this change.** They belong to stages, and stages are not being touched. The `README.md` in `agents/` shows a minimal usage example (scratch script) so a reader can see the intended call shape without any stage being rewired.

- **New env fields — read only by `AgentSettings`**, not added to `foundry.config.Settings`:
  - `CODING_AGENT=stub|claude_cli|opencode|codex_cli` (default `stub`)
  - `AGENT_TIMEOUT_SEC=600`
  - `AGENT_MAX_TURNS_PLAN=5`, `AGENT_MAX_TURNS_IMPLEMENT=30`, `AGENT_MAX_TURNS_VERIFY=5`
  - `AGENT_MODEL` — optional model override (semantics per backend; `claude_cli` ignores)
  Keeping these out of `foundry.config.Settings` until the pipeline actually depends on them means this change remains a pure addition.

- **Invariants every backend upholds** (convention + adapter code, not types):
  - `apply()` does NOT commit, push, or switch/create branches.
  - `apply()` is synchronous with a hard timeout.
  - `ShellError` / `subprocess.TimeoutExpired` propagate as exceptions.
  - Caller builds the full prompt string; the adapter does not read template files.
  - Output is two text fields (`response` full, `result` first-line ≤ 200 chars) plus the stage echo.

- **Out of scope** — all of this lands in follow-up changes:
  - Wiring stages to the agent (replacing stub `plan`/`implement`/`verify` bodies).
  - Prompt templates at `src/foundry/stages/prompts/` (`plan.md`, `implement.md`, `verify.md`) including the `NEED_VERIFICATION` / `PASS` / `FAIL` conventions.
  - Dropping the `context` stage.
  - Any new task statuses, FSM changes, or pipeline edits.
  - Human-in-the-loop clarification flow.
  - Retry loop (Day 5–6).
  - Cost / token caps as failure gates.
  - Persistent cross-process session state.
  - Aider backend.

## Capabilities

### New Capabilities

- `coding-agent`: a pluggable LLM-coding-agent abstraction shipped as a standalone package. Defines the `CodingAgent` protocol; the `AgentStage` enum (`PLAN`/`IMPLEMENT`/`VERIFY`); the `AgentTask` and `AgentResult` data shapes; the per-task instantiation pattern (`make_agent(agent_settings, task_id)`); the in-adapter session-state semantics (private in-memory dict keyed by stage); and the backend invariants (no commits, no branch changes, no pushes; strings in, strings out; synchronous `apply()` with a hard timeout; exceptions propagate, no silent failures). This change ships the package and its unit tests only; callers of the capability are added in follow-up changes.

### Modified Capabilities

(None — `openspec/specs/` is empty and no existing capability is being redefined.)

## Impact

- **Code — new, all under `src/foundry/agents/`**:
  - `__init__.py`, `base.py`, `config.py`, `factory.py`
  - `stub.py`, `claude_cli.py`, `opencode_cli.py`, `codex_cli.py`
  - `README.md` — short usage example targeting a future caller (scratch script style), so a reader can see the intended call shape
- **Code — modified**: **none**. Existing `src/foundry/stages/*.py`, `pipeline.py`, `config.py`, `models.py`, `state.py`, and all current tests are untouched.
- **Tests — new**, all under `tests/`:
  - `test_agents_stub.py` — end-to-end-ish on a tmp worktree: PLAN/VERIFY fixed strings; IMPLEMENT appends a line to README and returns a first-line summary
  - `test_agents_claude_cli.py` — mocks `subprocess.run`, feeds canned `stream-json` fixtures; asserts the session id is captured on the first call and echoed back as `--resume <id>` on the second call for the same `AgentStage`
  - `test_agents_opencode.py` — same shape for opencode's `--format json` events
  - `test_agents_codex_cli.py` — same shape for codex's `--json` events; additionally asserts the adapter switches between `codex exec` and `codex exec resume <id>` based on stored session state
- **Tests — modified**: none. Existing `tests/test_pipeline.py`, `test_implement.py`, `test_state.py`, etc. keep passing unchanged.
- **Dependencies**: no new Python packages. Runtime binary requirements are only exercised in manual testing for now — `stub` is dependency-free and the only backend used by CI.
- **Auth**: no new auth plumbing in the pipeline. Manual setup steps documented in `agents/README.md`:
  - `claude_cli` → one-time `claude login` (Anthropic Pro/Max).
  - `opencode` → provider env vars (`ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, ...).
  - `codex_cli` → `codex login` (ChatGPT Plus/Pro) or `codex login --with-api-key` reading `OPENAI_API_KEY`.
- **Docs**: no changes to `CLAUDE.md` or `DEBUG.md` yet (they'd describe end-to-end usage, which still runs the old stubs). `docs/architecture/agent-protocol.md` stays as-is; the follow-up wiring change will reconcile it with the final contract.
- **Pipeline FSM**: unchanged. `foundry run` still executes the stubs exactly as today.
- **Data model**: unchanged. No SQLite schema touched. No migration.
