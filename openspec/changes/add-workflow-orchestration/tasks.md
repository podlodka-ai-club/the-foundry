## 1. Workflow Skeleton

- [x] 1.1 Add minimal workflow/orchestration types for workflow name, step result, and verification decision without introducing external dependencies.
- [x] 1.2 Refactor the existing issue-driven `_process_task` path into a `dev_task` workflow helper while preserving current `foundry run` behavior.
- [x] 1.3 Keep existing `stage_span`, `record_event`, `append_log`, and task status updates compatible with current API/UI projections.
- [x] 1.4 Add tests that the refactored `dev_task` happy path still opens a PR and emits the same stage event sequence.

## 2. Quality Gate Retry Loop

- [x] 2.1 Introduce normalized verification result handling with `passed`, `retryable`, `requires_human`, `failure_kind`, and `report` fields.
- [x] 2.2 Add a bounded `implement -> verify` attempt loop to `dev_task`.
- [x] 2.3 Pass prior implementation summary and verification report into subsequent implementation attempts.
- [x] 2.4 Record attempt number and verification decision in `task_events` or logs so attempts are observable.
- [x] 2.5 Add tests for pass on first attempt, pass after retry, exhausted retries, and human-blocked verification.

## 3. PR Verification Workflow

- [x] 3.1 Add a `pr_verify` workflow entrypoint that runs verification against an existing task/worktree context.
- [x] 3.2 Ensure `pr_verify` records verification events and returns a PR-facing report.
- [x] 3.3 Ensure `pr_verify` does not call the PR creation stage, does not close the source issue, and does not mark the task `DONE`.
- [x] 3.4 Add tests for successful and failed `pr_verify` runs.

## 4. Future Outcome Boundaries

- [x] 4.1 Document planner outcome names (`plan_ready`, `needs_input`, `declined`, `decompose`) in code or docs as future-facing contracts.
- [x] 4.2 Add conservative handling for unknown/unsupported planner outcomes if the implementation touches planner normalization.
- [x] 4.3 Keep decomposition, parallel implementations, merge conflict resolution, deploy, Discord intent routing, and agentic code review out of this implementation unless a later change explicitly scopes them in.

## 5. Verification

- [x] 5.1 Run focused pipeline/workflow tests.
- [x] 5.2 Run `uv run pytest`.
- [x] 5.3 Update `DEBUG.md` or architecture docs with the new workflow model and how to manually exercise `dev_task` and `pr_verify`.
