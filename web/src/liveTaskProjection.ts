import type { UiEvent, UiStage, UiTask } from "./api";

function copyStage(stage: UiStage | undefined, stageId: string): UiStage {
  return stage ? { ...stage } : { name: stageId, status: "pending" };
}

export function projectLiveTask(task: UiTask, events: UiEvent[]): UiTask {
  if (events.length === 0) return task;

  const stages: Record<string, UiStage> = {};
  for (const [stageId, stage] of Object.entries(task.stages)) {
    stages[stageId] = { ...stage };
  }

  let currentStage = task.current_stage;
  let hasRunningStage = false;

  for (const event of events) {
    const stageId = event.stage;
    const payload = event.payload ?? {};

    if (event.kind === "stage_started") {
      const stage = copyStage(stages[stageId], stageId);
      stage.status = "running";
      if ("agent" in payload) stage.agent = payload.agent as UiStage["agent"];
      if ("input" in payload) stage.input = payload.input as UiStage["input"];
      stages[stageId] = stage;
      currentStage = stageId;
      hasRunningStage = true;
      continue;
    }

    if (event.kind === "stage_finished") {
      const stage = copyStage(stages[stageId], stageId);
      stage.status = "done";
      if ("duration_ms" in payload) stage.duration_ms = payload.duration_ms as number;
      if ("cost_usd" in payload) stage.cost_usd = payload.cost_usd as number;
      if ("tokens_in" in payload) stage.tokens_in = payload.tokens_in as number;
      if ("tokens_out" in payload) stage.tokens_out = payload.tokens_out as number;
      if ("output" in payload) stage.output = payload.output as UiStage["output"];
      stages[stageId] = stage;
      hasRunningStage = Object.values(stages).some((s) => s.status === "running");
      continue;
    }

    if (event.kind === "stage_failed") {
      const stage = copyStage(stages[stageId], stageId);
      stage.status = "failed";
      if ("error" in payload) stage.error = String(payload.error ?? "");
      if ("duration_ms" in payload) stage.duration_ms = payload.duration_ms as number;
      stages[stageId] = stage;
      currentStage = stageId;
      hasRunningStage = false;
    }
  }

  return {
    ...task,
    status: hasRunningStage ? "running" : task.status,
    current_stage: currentStage,
    stages,
    events,
  };
}
