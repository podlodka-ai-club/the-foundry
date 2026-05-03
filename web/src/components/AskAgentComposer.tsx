// AskAgentComposer — UI-only stub for PR6.
// The actual POST endpoint is deliberately out of scope (see
// docs/specs/observability-ui-plan.md, PR6 → "Не делаем: POST /ask").

import type { JSX } from "react";
import { useState } from "react";
import { ChevronRight, Lightbulb } from "lucide-react";

import type { AgentInfo } from "../api";

interface Props {
  agent?: AgentInfo | null;
  stageLabel: string;
}

export default function AskAgentComposer({ agent, stageLabel }: Props): JSX.Element {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const agentName = agent?.name ?? "агента";

  return (
    <div
      style={{
        borderTop: "1px solid var(--border)",
        background: "var(--bg-1)",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          padding: "12px 14px",
          background: "transparent",
          border: 0,
          cursor: "pointer",
          textAlign: "left",
          color: "inherit",
          font: "inherit",
        }}
      >
        <Lightbulb
          className="ico-sm"
          style={{ color: "var(--highlight)" }}
        />
        <span
          style={{
            fontSize: 11,
            letterSpacing: ".06em",
            textTransform: "uppercase",
            color: "var(--fg-2)",
            fontWeight: 600,
          }}
        >
          Спросить у агента
        </span>
        <span style={{ flex: 1 }} />
        <ChevronRight
          className="ico-sm"
          style={{
            color: "var(--fg-2)",
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform .18s cubic-bezier(.2,.7,.3,1)",
          }}
        />
      </button>
      {open && (
        <div style={{ padding: "0 14px 12px" }}>
          <div
            style={{
              fontSize: 11,
              color: "var(--fg-3)",
              marginBottom: 8,
            }}
          >
            контекст стадии{" "}
            <span className="mono" style={{ color: "var(--fg-1)" }}>
              {stageLabel}
            </span>{" "}
            прикладывается автоматически
          </div>
          <div
            style={{
              border: "1px solid var(--border-strong)",
              borderRadius: "var(--r-md)",
              background: "var(--bg-0)",
              padding: 10,
            }}
          >
            <textarea
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={`Уточнить у ${agentName} — что именно сделано и почему`}
              rows={3}
              style={{
                width: "100%",
                background: "transparent",
                border: 0,
                outline: 0,
                resize: "none",
                color: "var(--fg-0)",
                font: "inherit",
                fontSize: 13,
                lineHeight: 1.5,
              }}
            />
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginTop: 6,
                paddingTop: 8,
                borderTop: "1px solid var(--border-soft)",
              }}
            >
              <span className="hint">⌘+Enter — отправить</span>
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className="topbar-btn primary"
                disabled
                title="скоро будет"
                style={{ opacity: 0.5, cursor: "not-allowed" }}
              >
                Отправить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
