import type { CSSProperties, JSX } from "react";
import { Fragment } from "react";
import { Check, X } from "lucide-react";

import { STAGES } from "../stages";
import type { UiStage } from "../api";

type Size = "sm" | "md" | "lg";

interface Props {
  stages: Record<string, UiStage>;
  current?: string | null;
  size?: Size;
  showLabels?: boolean;
  onStageClick?: (stageId: string) => void;
  selectedStage?: string | null;
}

const SIZES: Record<Size, { dot: number; gap: number; labelFs: number; connH: number }> = {
  sm: { dot: 6, gap: 28, labelFs: 10, connH: 1 },
  md: { dot: 8, gap: 36, labelFs: 10.5, connH: 1 },
  lg: { dot: 12, gap: 64, labelFs: 11, connH: 1.5 },
};

export default function StageStepper({
  stages,
  size = "md",
  showLabels = false,
  onStageClick,
  selectedStage,
}: Props): JSX.Element {
  const sizes = SIZES[size];

  return (
    <div style={{ display: "flex", alignItems: "center" }}>
      {STAGES.map((s, idx) => {
        const st = stages[s.id] ?? { name: s.id, status: "pending" as const };
        const isDone = st.status === "done";
        const isRunning = st.status === "running";
        const isFailed = st.status === "failed";

        let dotColor = "var(--fg-3)";
        let ring = false;
        let content: JSX.Element | null = null;
        if (isDone) {
          dotColor = "var(--success)";
          content = <Check style={{ width: 7, height: 7, color: "#fff", strokeWidth: 3 }} />;
        }
        if (isRunning) {
          dotColor = "var(--running)";
          ring = true;
        }
        if (isFailed) {
          dotColor = "var(--danger)";
          content = <X style={{ width: 7, height: 7, color: "#fff", strokeWidth: 3 }} />;
        }

        // Connector color depends ONLY on the left-hand stage, so the line
        // doesn't flicker when the right-hand neighbor changes state.
        const connColor = isDone ? "var(--success)" : "var(--border-strong)";

        const dotSize = sizes.dot + 6;
        const isSelected = selectedStage === s.id;
        const clickable = typeof onStageClick === "function";
        const runRing = ring ? "0 0 0 3px var(--running-soft)" : "none";
        const dotStyle: CSSProperties = {
          width: dotSize,
          height: dotSize,
          borderRadius: "50%",
          background: dotColor,
          display: "grid",
          placeItems: "center",
          boxShadow: runRing,
          // Selection outline sits outside the dot with a transparent gap, so
          // it stays readable against any dot colour and any row background.
          outline: isSelected ? "2px solid var(--accent)" : "none",
          outlineOffset: isSelected ? 2 : 0,
          animation: ring ? "pulse-dot 1.4s ease-in-out infinite" : "none",
          flexShrink: 0,
          cursor: clickable ? "pointer" : "default",
          transition: "transform .15s, outline-color .15s",
        };

        const labelStyle: CSSProperties = {
          position: "absolute",
          top: dotSize + 6,
          fontSize: sizes.labelFs,
          color: isRunning
            ? "var(--running)"
            : isDone
              ? "var(--fg-1)"
              : isFailed
                ? "var(--danger)"
                : "var(--fg-3)",
          fontWeight: isRunning || isFailed ? 600 : 400,
          letterSpacing: ".01em",
          whiteSpace: "nowrap",
        };

        const labelGap = showLabels ? dotSize + 22 : 0;
        return (
          <Fragment key={s.id}>
            <div
              style={{
                position: "relative",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                paddingBottom: labelGap,
              }}
            >
              <div
                role={clickable ? "button" : undefined}
                tabIndex={clickable ? 0 : undefined}
                onClick={
                  clickable
                    ? (e) => {
                        e.stopPropagation();
                        onStageClick?.(s.id);
                      }
                    : undefined
                }
                onKeyDown={
                  clickable
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onStageClick?.(s.id);
                        }
                      }
                    : undefined
                }
                style={dotStyle}
              >
                {content}
              </div>
              {showLabels && <span style={labelStyle}>{s.label}</span>}
            </div>
            {idx < STAGES.length - 1 && (
              <div
                style={{
                  width: sizes.gap,
                  height: sizes.connH,
                  background: connColor,
                  flexShrink: 0,
                  transition: "background .3s",
                  // Compensate the parent's paddingBottom (used to reserve
                  // space for the label) so the connector stays horizontally
                  // aligned with the center of the dots.
                  marginBottom: labelGap,
                }}
              />
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
