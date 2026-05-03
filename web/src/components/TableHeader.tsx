import type { JSX } from "react";

import { ROW_GRID } from "./gridTemplate";

export default function TableHeader(): JSX.Element {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: ROW_GRID,
        alignItems: "center",
        gap: 14,
        padding: "8px 20px 8px 22px",
        borderBottom: "1px solid var(--border)",
        background: "var(--bg-0)",
        position: "sticky",
        top: 44,
        zIndex: 5,
        fontSize: 10,
        letterSpacing: ".08em",
        textTransform: "uppercase",
        fontWeight: 600,
        color: "var(--fg-2)",
      }}
    >
      <span />
      <span>Статус</span>
      <span>Задача</span>
      <span>Стадии</span>
      <span style={{ justifySelf: "end" }}>Длит.</span>
      <span style={{ justifySelf: "end" }}>Стоимость</span>
    </div>
  );
}
