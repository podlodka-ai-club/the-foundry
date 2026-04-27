## ADDED Requirements

### Requirement: Named workflow routing
The system SHALL route supported orchestration inputs to explicit named workflows instead of embedding every mode as ad hoc branches in the development pipeline.

#### Scenario: Labeled issue starts dev task workflow
- **WHEN** `foundry run` fetches a labeled issue task
- **THEN** the system runs the task through the `dev_task` workflow

#### Scenario: PR verification request starts PR verification workflow
- **WHEN** the system is asked to verify an existing PR context
- **THEN** the system runs the `pr_verify` workflow instead of opening a new PR

### Requirement: Workflow execution remains observable
The system SHALL record workflow step execution through `task_events` so the UI can show stage starts, finishes, failures, inputs, outputs, attempts, agent metadata, and costs without reading a separate graph runtime.

#### Scenario: Workflow step emits standard events
- **WHEN** a workflow step starts and finishes successfully
- **THEN** the system records `stage_started` and `stage_finished` events for the task

#### Scenario: Workflow step failure is visible
- **WHEN** a workflow step fails
- **THEN** the system records `stage_failed` with enough payload data to identify the failed stage and reason

### Requirement: Workflow transitions are controlled by the orchestrator
The system SHALL allow agents to return typed outcomes, but the orchestrator MUST validate those outcomes and execute only allowlisted workflow transitions.

#### Scenario: Planner requests more input
- **WHEN** the planner returns a `needs_input` outcome
- **THEN** the orchestrator stops the executable workflow path and records that user input is required

#### Scenario: Planner proposes decomposition
- **WHEN** the planner returns a `decompose` outcome
- **THEN** the orchestrator records the decomposition request without executing arbitrary agent-defined steps

### Requirement: Existing issue processing remains compatible
The system SHALL preserve the existing `foundry run` behavior for labeled issue tasks while moving the implementation behind a named workflow.

#### Scenario: Existing happy path still opens PR
- **WHEN** a fetched task passes context, plan, implement, verify, and PR stages
- **THEN** the task is marked `done` and stores the opened PR URL as before
