import type { JSX } from "react";
import { Sparkles } from "lucide-react";

import type { AgentInfo } from "../api";

interface Props {
  agent: AgentInfo;
}

export default function AgentBadge({ agent }: Props): JSX.Element {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 8px 3px 4px",
        borderRadius: 999,
        background: "var(--bg-0)",
        border: "1px solid var(--border)",
        fontSize: 11,
      }}
    >
      <span
        style={{
          width: 18,
          height: 18,
          borderRadius: "50%",
          background: "var(--accent)",
          display: "grid",
          placeItems: "center",
          color: "#fff",
        }}
      >
        <Sparkles style={{ width: 10, height: 10 }} />
      </span>
      {agent.name && <span style={{ color: "var(--fg-0)", fontWeight: 500 }}>{agent.name}</span>}
      {agent.model && (
        <>
          <span style={{ color: "var(--fg-3)" }}>·</span>
          <span className="mono" style={{ color: "var(--fg-1)", fontSize: 10.5 }}>
            {agent.model}
          </span>
        </>
      )}
    </div>
  );
}
