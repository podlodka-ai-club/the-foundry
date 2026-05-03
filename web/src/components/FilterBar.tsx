import type { JSX } from "react";

export type TaskFilter = "all" | "active" | "done" | "failed";

interface Props {
  value: TaskFilter;
  onChange: (value: TaskFilter) => void;
  counts: Record<TaskFilter, number>;
}

const OPTIONS: Array<{ id: TaskFilter; label: string; withRunningDot?: boolean }> = [
  { id: "all", label: "Все" },
  { id: "active", label: "Активные", withRunningDot: true },
  { id: "done", label: "Успешные" },
  { id: "failed", label: "Упавшие" },
];

export default function FilterBar({ value, onChange, counts }: Props): JSX.Element {
  return (
    <div className="toolbar">
      {OPTIONS.map((opt) => (
        <button
          key={opt.id}
          type="button"
          className={`filter-pill${value === opt.id ? " active" : ""}`}
          onClick={() => onChange(opt.id)}
        >
          {opt.withRunningDot && <span className="dot dot-running" />}
          {opt.label}
          <span style={{ color: "var(--fg-3)", marginLeft: 2 }}>{counts[opt.id]}</span>
        </button>
      ))}
    </div>
  );
}
