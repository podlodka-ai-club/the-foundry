// TaskDetails — inline expanded panel under a task row.
// Shows issue meta, a clickable stage stepper, and the StageDetailPanel
// for the currently selected stage.

import type { JSX } from "react";
import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Folder, GitBranch, Hash, RotateCcw } from "lucide-react";

import { resetTask } from "../api";
import type { UiEvent, UiTask } from "../api";
import { STAGES } from "../stages";
import StageDetailPanel from "./StageDetailPanel";
import StageStepper from "./StageStepper";

interface Props {
  task: UiTask;
  events: UiEvent[];
  connected: boolean;
  streamError: string | null;
}

function pickDefaultStage(task: UiTask): string {
  // running > failed > last done > current_stage > first
  for (const s of STAGES) {
    if (task.stages[s.id]?.status === "running") return s.id;
  }
  for (const s of STAGES) {
    if (task.stages[s.id]?.status === "failed") return s.id;
  }
  let last: string | null = null;
  for (const s of STAGES) {
    if (task.stages[s.id]?.status === "done") last = s.id;
  }
  if (last) return last;
  if (task.current_stage && STAGES.some((s) => s.id === task.current_stage)) {
    return task.current_stage;
  }
  return STAGES[0].id;
}

function formatMemoryValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value
      .map((item) =>
        typeof item === "object" && item !== null ? JSON.stringify(item) : String(item),
      )
      .join(", ");
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value ?? "");
}

export default function TaskDetails({
  task,
  events,
  connected,
  streamError,
}: Props): JSX.Element {
  const defaultStage = useMemo(() => pickDefaultStage(task), [task]);
  const [selectedStage, setSelectedStage] = useState<string>(defaultStage);
  const [userPicked, setUserPicked] = useState(false);
  const activeStage = userPicked ? selectedStage : defaultStage;

  const stageEvents = events.filter((e) => e.stage === activeStage);
  const issueUrl = `https://github.com/${task.repo}/issues/${task.issue_number}`;
  const queryClient = useQueryClient();
  const resetMutation = useMutation({
    mutationFn: () => resetTask(task.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["repos"] });
    },
  });
  const canReset = task.status.toUpperCase() !== "RUNNING";

  const onReset = (): void => {
    if (!canReset || resetMutation.isPending) return;
    const ok = window.confirm(
      `Сбросить задачу #${task.issue_number} в pending/fetch для повторного запуска?`,
    );
    if (ok) resetMutation.mutate();
  };

  return (
    <div
      style={{
        background: "var(--bg-0)",
        borderTop: "1px solid var(--border)",
        padding: "16px 24px 18px",
        display: "flex",
        flexDirection: "column",
        gap: 14,
      }}
    >
      {/* Meta header */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto",
          gap: 16,
          alignItems: "flex-start",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: "var(--fg-0)",
              lineHeight: 1.4,
            }}
          >
            <span className="mono" style={{ color: "var(--accent)", marginRight: 6 }}>
              #{task.issue_number}
            </span>
            {task.issue_title}
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              marginTop: 2,
              fontSize: 11.5,
              color: "var(--fg-2)",
              flexWrap: "wrap",
            }}
          >
            <span
              className="mono"
              style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
            >
              <Hash className="ico-sm" />
              {task.repo}
            </span>
            {task.branch_name && (
              <span
                className="mono"
                style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
                title={task.branch_name}
              >
                <GitBranch className="ico-sm" />
                {task.branch_name}
              </span>
            )}
            {task.worktree_path && (
              <span
                className="mono ellipsis"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  maxWidth: 360,
                }}
                title={task.worktree_path}
              >
                <Folder className="ico-sm" />
                {task.worktree_path}
              </span>
            )}
            <a
              href={issueUrl}
              target="_blank"
              rel="noreferrer noopener"
              onClick={(e) => e.stopPropagation()}
              className="mono"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                color: "var(--fg-1)",
              }}
            >
              открыть issue
              <ExternalLink className="ico-sm" style={{ opacity: 0.6 }} />
            </a>
            {task.pr_url && (
              <a
                href={task.pr_url}
                target="_blank"
                rel="noreferrer noopener"
                onClick={(e) => e.stopPropagation()}
                className="mono"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  color: "var(--accent)",
                }}
              >
                PR
                <ExternalLink className="ico-sm" style={{ opacity: 0.6 }} />
              </a>
            )}
          </div>
          {streamError && (
            <div
              style={{
                fontSize: 11,
                color: "var(--danger)",
              }}
            >
              Поток событий: {streamError}
            </div>
          )}
          {resetMutation.error && (
            <div
              style={{
                fontSize: 11,
                color: "var(--danger)",
              }}
            >
              Сброс не удался:{" "}
              {resetMutation.error instanceof Error
                ? resetMutation.error.message
                : String(resetMutation.error)}
            </div>
          )}
        </div>
        <button
          type="button"
          className="topbar-btn"
          onClick={(e) => {
            e.stopPropagation();
            onReset();
          }}
          disabled={!canReset || resetMutation.isPending}
          title={
            canReset
              ? "Сбросить задачу в pending/fetch"
              : "Running-задачу нельзя сбросить"
          }
          style={{
            opacity: !canReset || resetMutation.isPending ? 0.55 : 1,
            cursor: !canReset || resetMutation.isPending ? "not-allowed" : "pointer",
            whiteSpace: "nowrap",
          }}
        >
          {resetMutation.isPending ? (
            <span className="spinner" />
          ) : (
            <RotateCcw className="ico-sm" />
          )}
          Reset
        </button>
      </div>

      {task.memory.length > 0 && (
        <div className="card" style={{ padding: "14px 18px" }}>
          <div
            style={{
              fontSize: 10,
              letterSpacing: ".1em",
              textTransform: "uppercase",
              color: "var(--fg-2)",
              fontWeight: 600,
              marginBottom: 10,
            }}
          >
            Repo memory
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {task.memory.map((entry) => (
              <div
                key={entry.key}
                style={{
                  display: "grid",
                  gridTemplateColumns: "150px 1fr",
                  gap: 12,
                  minWidth: 0,
                  fontSize: 11.5,
                }}
              >
                <span className="mono" style={{ color: "var(--fg-1)" }}>
                  {entry.key}
                </span>
                <span
                  className="mono ellipsis"
                  style={{ color: "var(--fg-2)" }}
                  title={formatMemoryValue(entry.value)}
                >
                  {formatMemoryValue(entry.value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stage timeline */}
      <div className="card" style={{ padding: "16px 22px 12px", position: "relative" }}>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginBottom: 18,
          }}
        >
          <span
            style={{
              fontSize: 10,
              letterSpacing: ".1em",
              textTransform: "uppercase",
              color: "var(--fg-2)",
              fontWeight: 600,
            }}
          >
            Таймлайн стадий
          </span>
          <span
            style={{
              fontSize: 11,
              color: connected ? "var(--success)" : "var(--fg-3)",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {connected ? (
              <>
                <span className="dot dot-done" style={{ width: 6, height: 6 }} />
                live
              </>
            ) : (
              "кликните на стадию, чтобы увидеть детали"
            )}
          </span>
        </div>
        <div style={{ paddingLeft: 4, paddingBottom: 6 }}>
          <StageStepper
            stages={task.stages}
            current={task.current_stage}
            size="lg"
            showLabels
            selectedStage={activeStage}
            onStageClick={(sid) => {
              setSelectedStage(sid);
              setUserPicked(true);
            }}
          />
        </div>
      </div>

      {/* Stage detail */}
      <StageDetailPanel task={task} stageId={activeStage} events={stageEvents} />
    </div>
  );
}
