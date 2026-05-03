## ADDED Requirements

### Requirement: Development workflow has bounded implementation attempts
The `dev_task` workflow SHALL run implementation and verification as a bounded attempt loop.

#### Scenario: First attempt passes verification
- **WHEN** the first implementation attempt passes verification
- **THEN** the workflow proceeds to PR creation without running another implementation attempt

#### Scenario: Retryable verification failure is retried
- **WHEN** verification fails with a retryable result and the attempt budget is not exhausted
- **THEN** the workflow runs another implementation attempt using the previous verification report as feedback

#### Scenario: Attempt budget is exhausted
- **WHEN** verification fails and the maximum number of implementation attempts has been reached
- **THEN** the workflow marks the task as failed and does not open a PR

### Requirement: Verification results are structured
The system SHALL normalize verifier output into a structured result that includes whether verification passed, whether failure is retryable, whether human input is required, a failure kind, and a report.

#### Scenario: Passing verification
- **WHEN** verifier checks pass
- **THEN** the normalized result has `passed=true` and includes a human-readable report

#### Scenario: Human input required
- **WHEN** verifier determines the task is unclear or unsafe to continue automatically
- **THEN** the normalized result has `requires_human=true` and the workflow stops without another implementation attempt

#### Scenario: Infrastructure failure
- **WHEN** verification fails because of infrastructure rather than code behavior
- **THEN** the workflow treats the failure according to orchestration retry policy instead of counting it as a successful code-quality verdict

### Requirement: Retry attempts receive verifier feedback
The system SHALL pass prior verification feedback into subsequent implementation attempts.

#### Scenario: Second attempt receives first attempt report
- **WHEN** the first implementation attempt fails verification retryably
- **THEN** the second implementation attempt receives the previous implementation summary and verification report in its input context

### Requirement: PR verification is separate from PR creation
The system SHALL support verifying an existing PR context without committing, pushing, opening a new PR, or closing the source issue.

#### Scenario: PR verify produces report only
- **WHEN** the `pr_verify` workflow runs against an existing PR/worktree context
- **THEN** the system runs verification and returns or records a PR-facing report

#### Scenario: PR verify does not call PR stage
- **WHEN** the `pr_verify` workflow completes
- **THEN** the system does not call the PR creation stage
