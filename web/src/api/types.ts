// Wire types — mirror src/api/models.py (Pydantic v2). Kept hand-written so we
// stay TS-strict; if either side changes, update both.

export type RunStatus =
  | 'pending'
  | 'running'
  | 'waiting'
  | 'done'
  | 'failed'
  | 'unclear';

export type FailureKind =
  | 'deterministic'
  | 'acceptance'
  | 'infra'
  | 'unclear'
  | 'dangerous';

export interface UiAutomationCounts {
  running: number;
  waiting: number;
  pending: number;
  total: number;
}

export interface UiAutomation {
  id: string;
  name: string;
  description: string;
  triggers: string[];
  skills: string[];
  agent: Record<string, unknown>;
  counts: UiAutomationCounts;
}

export interface UiTrigger {
  id: string;
  source: string;
  kind: string;
  last_seen: string | null;
  health: 'ok' | 'stale' | null;
}

export interface UiRunTrigger {
  source: string;
  external_id: string;
  text: string;
  author: string | null;
  kind: string;
}

export interface UiRun {
  id: number;
  automation_id: string;
  event_id: number;
  session_id: string;
  session_seq: number;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  duration_sec: number | null;
  cost_usd: number | null;
  failure_kind: FailureKind | null;
  failure_msg: string | null;
  waiting_reason: string | null;
  agent_session_id: string | null;
  trigger: UiRunTrigger | null;
}

export interface UiEvent {
  seq: number;
  run_id: number;
  stage: string;
  kind: string;
  ts_ms: number;
  payload: Record<string, unknown>;
  parent_event_seq: number | null;
}

export interface UiRunDetail extends UiRun {
  events: UiEvent[];
}

export type RunsFilter = 'all' | 'running' | 'waiting' | 'failed';

export interface PostMessageBody {
  type: 'continue' | 'enqueue' | 'reply';
  text: string;
}
