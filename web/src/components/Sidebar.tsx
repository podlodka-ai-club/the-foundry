import type { JSX } from "react";
import { Inbox, GitBranch, Calendar } from "lucide-react";

import type { RepoCount, UiTask } from "../api";
import { formatTokens } from "../utils";

interface Props {
  repos: RepoCount[];
  tasks: UiTask[];
}

export default function Sidebar({ repos, tasks }: Props): JSX.Element {
  // Rough "today" spend proxy: sum tokens over DONE tasks.
  // TODO PR6: filter by updated_at within the current calendar day.
  const todayTokens = tasks
    .filter((t) => t.status.toUpperCase() === "DONE")
    .reduce(
      (acc, t) => acc + (t.tokens_in_total ?? 0) + (t.tokens_out_total ?? 0),
      0,
    );

  return (
    <aside className="sidebar" style={{ width: 232, flexShrink: 0 }}>
      <div className="sidebar-brand">
        <span className="sidebar-brand-logo">F</span>
        <span className="sidebar-brand-name">Foundry</span>
      </div>

      <div className="sidebar-section">Навигация</div>
      <div className="nav-item active">
        <Inbox />
        <span>Задачи</span>
        <span className="count">{tasks.length}</span>
      </div>

      <div className="sidebar-section">Репозитории</div>
      {repos.length === 0 && (
        <div style={{ padding: "4px 8px", color: "var(--fg-3)", fontSize: 12 }}>—</div>
      )}
      {repos.map((r) => {
        const total =
          r.counts.RUNNING + r.counts.DONE + r.counts.FAILED + r.counts.PENDING;
        return (
          <div key={r.repo} className="nav-item" title={r.repo}>
            <GitBranch />
            <span
              className="ellipsis"
              style={{ minWidth: 0, flex: 1 }}
            >
              {r.repo.split("/").pop() ?? r.repo}
            </span>
            <span className="count">{total}</span>
          </div>
        );
      })}

      <div className="sidebar-section">Сегодня</div>
      <div
        style={{
          margin: "4px 8px 8px",
          padding: "10px 12px",
          background: "var(--bg-2)",
          border: "1px solid var(--border)",
          borderRadius: "var(--r-md)",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <Calendar
          style={{ width: 14, height: 14, color: "var(--fg-2)", flexShrink: 0 }}
        />
        <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
          <span style={{ fontSize: 11, color: "var(--fg-2)" }}>расход</span>
          <span
            className="tabular"
            style={{ fontSize: 13, color: "var(--fg-0)", fontWeight: 500 }}
          >
            {formatTokens(todayTokens)} ток.
          </span>
        </div>
      </div>
    </aside>
  );
}
