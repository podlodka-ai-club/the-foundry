// API client for the Foundry observability UI.
// Types mirror `src/api/projections.py` (Pydantic models).

export type StageStatus = "pending" | "running" | "done" | "failed";

export interface AgentInfo {
  name?: string;
  model?: string;
  provider?: string;
  [key: string]: unknown;
}

export interface UiStage {
  name: string;
  status: StageStatus;
  duration_ms?: number | null;
  cost_usd?: number | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  agent?: AgentInfo | null;
  input?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  error?: string | null;
}

export interface UiEvent {
  seq: number;
  stage: string;
  kind: string;
  ts_ms: number;
  payload: Record<string, unknown>;
}

export interface UiMemoryEntry {
  repo: string;
  key: string;
  value: unknown;
  updated_at: string;
}

export interface UiTask {
  id: number;
  repo: string;
  issue_number: number;
  issue_title: string;
  status: string;
  current_stage: string;
  attempts: number;
  pr_url: string | null;
  branch_name: string | null;
  worktree_path: string | null;
  updated_at: string | null;
  created_at: string | null;
  total_cost_usd: number;
  tokens_in_total: number;
  tokens_out_total: number;
  duration_ms_total: number;
  stages: Record<string, UiStage>;
  memory: UiMemoryEntry[];
  events?: UiEvent[] | null;
}

export interface RepoCount {
  repo: string;
  counts: {
    RUNNING: number;
    DONE: number;
    FAILED: number;
    PENDING: number;
  };
}

const BASE_URL: string = import.meta.env.VITE_API_URL ?? "";

export function apiUrl(path: string): string {
  return `${BASE_URL}${path}`;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(apiUrl(path));
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function fetchTasks(): Promise<UiTask[]> {
  return getJson<UiTask[]>("/api/tasks");
}

export function fetchTask(id: number): Promise<UiTask> {
  return getJson<UiTask>(`/api/tasks/${id}`);
}

export function fetchRepos(): Promise<RepoCount[]> {
  return getJson<RepoCount[]>("/api/repos");
}

export async function resetTask(id: number): Promise<UiTask> {
  const res = await fetch(apiUrl(`/api/tasks/${id}/reset`), { method: "POST" });
  if (!res.ok) {
    throw new Error(`reset task ${id} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as UiTask;
}

export async function triggerFetch(): Promise<{ fetched: number }> {
  const res = await fetch(apiUrl("/api/fetch"), { method: "POST" });
  if (!res.ok) {
    throw new Error(`fetch failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as { fetched: number };
}
