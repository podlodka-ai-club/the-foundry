import type { JSX } from "react";
import { ChevronRight } from "lucide-react";

import type { UiTask } from "../api";
import { projectLiveTask } from "../liveTaskProjection";
import { useTaskStream } from "../useTaskStream";
import { formatCost, formatDurationMs, formatTokens } from "../utils";
import StatusChip from "./StatusChip";
import StageStepper from "./StageStepper";
import TaskDetails from "./TaskDetails";
import { ROW_GRID } from "./gridTemplate";

interface Props {
  task: UiTask;
  expanded: boolean;
  onToggle: () => void;
}

export default function TaskRow({ task, expanded, onToggle }: Props): JSX.Element {
  const stream = useTaskStream(expanded ? task.id : null);
  const liveTask = projectLiveTask(task, stream.events);
  const isRunning = liveTask.status.toUpperCase() === "RUNNING";
  const tokensTotal =
    (liveTask.tokens_in_total ?? 0) + (liveTask.tokens_out_total ?? 0);

  return (
    <div style={{ borderBottom: "1px solid var(--border-soft)" }}>
      <div
        className={isRunning ? "selected-bar" : ""}
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
        style={{
          display: "grid",
          gridTemplateColumns: ROW_GRID,
          alignItems: "center",
          gap: 14,
          padding: "11px 20px 11px 22px",
          cursor: "pointer",
          background: expanded ? "var(--bg-1)" : "transparent",
          transition: "background .12s",
        }}
      >
        <ChevronRight
          className="ico-sm"
          style={{
            color: "var(--fg-2)",
            transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform .18s cubic-bezier(.2,.7,.3,1)",
            flexShrink: 0,
          }}
        />

        <StatusChip status={liveTask.status} />

        <div
          style={{
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          <div
            className="ellipsis"
            style={{ fontSize: 13, fontWeight: 500, color: "var(--fg-0)" }}
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
              gap: 8,
              color: "var(--fg-2)",
              fontSize: 11.5,
            }}
          >
            <span className="mono ellipsis" title={task.repo}>
              {task.repo}
            </span>
            {task.attempts > 1 && (
              <>
                <span style={{ color: "var(--fg-3)" }}>·</span>
                <span style={{ color: "var(--warning)" }}>
                  попытка {task.attempts}
                </span>
              </>
            )}
          </div>
        </div>

        <StageStepper
          stages={liveTask.stages}
          current={liveTask.current_stage}
          size="sm"
          showLabels={false}
        />

        <span
          className="tabular"
          style={{
            fontSize: 12,
            color: "var(--fg-1)",
            justifySelf: "end",
          }}
        >
          {isRunning && (
            <span
              className="dot dot-running"
              style={{ marginRight: 6, width: 5, height: 5 }}
            />
          )}
          {formatDurationMs(liveTask.duration_ms_total)}
        </span>

        <span
          style={{
            justifySelf: "end",
            display: "inline-flex",
            alignItems: "baseline",
            gap: 4,
            color: "var(--fg-1)",
            fontSize: 11.5,
          }}
          className="tabular"
        >
          <span>{formatCost(liveTask.total_cost_usd)}</span>
          <span style={{ color: "var(--fg-3)", fontSize: 10 }}>
            · {formatTokens(tokensTotal)}
          </span>
        </span>
      </div>

      {expanded && (
        <TaskDetails
          task={liveTask}
          events={stream.events}
          connected={stream.connected}
          streamError={stream.error}
        />
      )}
    </div>
  );
}
