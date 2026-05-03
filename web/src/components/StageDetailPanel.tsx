// StageDetailPanel — shows the header and a tabbed view of input / event
// stream / output for the currently selected stage of an expanded task.

import { useState, type JSX } from "react";
import { Activity, Check, Clock, X } from "lucide-react";

import type { UiEvent, UiStage, UiTask } from "../api";
import { STAGES } from "../stages";
import { formatCost, formatDurationMs, formatTokens } from "../utils";
import AgentBadge from "./AgentBadge";
import AskAgentComposer from "./AskAgentComposer";
import EventStream from "./EventStream";
import StageIO from "./StageIO";

interface Props {
  task: UiTask;
  stageId: string;
  events: UiEvent[];
}

const AGENT_STAGES = new Set(["agent_plan", "agent_implement"]);

type TabId = "input" | "stream" | "output";

function TabButton({
  active,
  onClick,
  icon,
  label,
  trailing,
}: {
  active: boolean;
  onClick: () => void;
  icon?: JSX.Element;
  label: string;
  trailing?: JSX.Element;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`stage-tab${active ? " stage-tab-active" : ""}`}
    >
      {icon}
      <span>{label}</span>
      {trailing}
    </button>
  );
}

export default function StageDetailPanel({ task, stageId, events }: Props): JSX.Element {
  const stage: UiStage = task.stages[stageId] ?? {
    name: stageId,
    status: "pending",
  };
  const stageMeta = STAGES.find((s) => s.id === stageId);
  const isAgentStage = AGENT_STAGES.has(stageId);
  const isPending = stage.status === "pending";
  const isRunning = stage.status === "running";
  const isFailed = stage.status === "failed";
  const isDone = stage.status === "done";
  const tokensTotal = (stage.tokens_in ?? 0) + (stage.tokens_out ?? 0);
  const defaultTab: TabId = isAgentStage ? "stream" : "output";
  const [activeTab, setActiveTab] = useState<TabId>(defaultTab);
  const visibleTab: TabId =
    !isAgentStage && activeTab === "stream" ? "output" : activeTab;

  if (isPending) {
    return (
      <div
        className="card"
        style={{
          padding: "22px 24px",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: "50%",
            background: "var(--bg-2)",
            display: "grid",
            placeItems: "center",
            color: "var(--fg-3)",
          }}
        >
          <Clock className="ico-sm" />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--fg-1)" }}>
            Стадия{" "}
            <span className="mono" style={{ color: "var(--fg-0)" }}>
              {stageMeta?.label ?? stageId}
            </span>{" "}
            — ещё не выполнялась
          </div>
          <div style={{ fontSize: 11.5, color: "var(--fg-2)", marginTop: 2 }}>
            Начнётся после завершения предыдущих стадий.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {/* Header */}
      <div
        style={{
          padding: "12px 18px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 12,
          background: isRunning
            ? "var(--running-soft)"
            : isFailed
              ? "var(--danger-soft)"
              : "var(--bg-1)",
        }}
      >
        <span
          style={{
            fontSize: 10,
            letterSpacing: ".1em",
            textTransform: "uppercase",
            fontWeight: 700,
            color: isRunning
              ? "var(--running)"
              : isFailed
                ? "var(--danger)"
                : "var(--success)",
          }}
        >
          {stageMeta?.title ?? stageId}
        </span>
        <span className="mono" style={{ color: "var(--fg-3)", fontSize: 11 }}>
          ·
        </span>
        {isRunning && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11.5,
              color: "var(--running)",
            }}
          >
            <span className="spinner" />
            идёт сейчас
          </span>
        )}
        {isDone && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              fontSize: 11.5,
              color: "var(--success)",
            }}
          >
            <Check className="ico-sm" />
            завершено
          </span>
        )}
        {isFailed && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              fontSize: 11.5,
              color: "var(--danger)",
            }}
          >
            <X className="ico-sm" />
            провал
          </span>
        )}
        <span style={{ flex: 1 }} />

        {stage.agent && <AgentBadge agent={stage.agent} />}

        <div
          className="tabular"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            fontSize: 11,
            color: "var(--fg-2)",
          }}
        >
          {stage.duration_ms != null && (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <Clock className="ico-sm" />
              {formatDurationMs(stage.duration_ms)}
            </span>
          )}
          {stage.cost_usd != null && stage.cost_usd > 0 && (
            <span>{formatCost(stage.cost_usd)}</span>
          )}
          {tokensTotal > 0 && (
            <span style={{ color: "var(--fg-3)" }}>{formatTokens(tokensTotal)} ток.</span>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <div className="stage-tabbar">
        <TabButton
          active={visibleTab === "input"}
          onClick={() => setActiveTab("input")}
          label="Вход"
        />
        {isAgentStage && (
          <TabButton
            active={visibleTab === "stream"}
            onClick={() => setActiveTab("stream")}
            icon={<Activity className="ico-sm" style={{ color: "var(--accent)" }} />}
            label="Поток событий"
            trailing={
              isRunning ? (
                <span
                  style={{
                    color: "var(--running)",
                    fontSize: 10.5,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  <span className="dot dot-running" style={{ width: 5, height: 5 }} />
                  live
                </span>
              ) : (
                <span className="mono dim" style={{ fontSize: 10.5 }}>
                  {events.length}
                </span>
              )
            }
          />
        )}
        <TabButton
          active={visibleTab === "output"}
          onClick={() => setActiveTab("output")}
          label="Выход"
        />
      </div>

      {/* Active tab content */}
      <div className="stage-tabpanel">
        {visibleTab === "input" && (
          <div style={{ padding: "12px 16px" }}>
            <StageIO kind="input" data={stage.input ?? null} />
          </div>
        )}
        {visibleTab === "stream" && isAgentStage && (
          <EventStream events={events} style="telegram" />
        )}
        {visibleTab === "output" && (
          <div style={{ padding: "12px 16px" }}>
            <StageIO kind="output" data={stage.output ?? null} />
          </div>
        )}
      </div>

      {/* Traceback */}
      {isFailed && stage.error && (
        <div style={{ padding: "0 14px 14px" }}>
          <pre className="trace">{stage.error}</pre>
        </div>
      )}

      {/* Composer stub (UI-only) */}
      {isAgentStage && <AskAgentComposer agent={stage.agent} stageLabel={stageMeta?.label ?? stageId} />}
    </div>
  );
}
