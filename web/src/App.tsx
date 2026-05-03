import type { JSX } from "react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Inbox } from "lucide-react";

import { fetchRepos, fetchTasks } from "./api";
import type { UiTask } from "./api";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import FilterBar from "./components/FilterBar";
import type { TaskFilter } from "./components/FilterBar";
import TableHeader from "./components/TableHeader";
import TaskRow from "./components/TaskRow";

const REFETCH_MS = 3000;
const EMPTY_TASKS: UiTask[] = [];
const EMPTY_REPOS: Awaited<ReturnType<typeof fetchRepos>> = [];

function matchesFilter(task: UiTask, filter: TaskFilter): boolean {
  const s = task.status.toUpperCase();
  if (filter === "all") return true;
  if (filter === "active") return s === "RUNNING" || s === "PENDING";
  if (filter === "done") return s === "DONE";
  if (filter === "failed") return s === "FAILED";
  return true;
}

export default function App(): JSX.Element {
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const tasksQuery = useQuery({
    queryKey: ["tasks"],
    queryFn: fetchTasks,
    refetchInterval: REFETCH_MS,
  });

  const reposQuery = useQuery({
    queryKey: ["repos"],
    queryFn: fetchRepos,
    refetchInterval: REFETCH_MS,
  });

  const tasks = tasksQuery.data ?? EMPTY_TASKS;
  const repos = reposQuery.data ?? EMPTY_REPOS;

  const counts = useMemo(() => {
    const out: Record<TaskFilter, number> = {
      all: tasks.length,
      active: 0,
      done: 0,
      failed: 0,
    };
    for (const t of tasks) {
      const s = t.status.toUpperCase();
      if (s === "RUNNING" || s === "PENDING") out.active += 1;
      if (s === "DONE") out.done += 1;
      if (s === "FAILED") out.failed += 1;
    }
    return out;
  }, [tasks]);

  const filtered = useMemo(
    () => tasks.filter((t) => matchesFilter(t, filter)),
    [tasks, filter],
  );

  const isLoading = tasksQuery.isLoading || reposQuery.isLoading;
  const loadError = tasksQuery.error ?? reposQuery.error;

  return (
    <div className="app-shell" style={{ gridTemplateColumns: "232px 1fr" }}>
      <Sidebar repos={repos} tasks={tasks} />
      <main className="main">
        <Topbar />
        <FilterBar value={filter} onChange={setFilter} counts={counts} />
        <TableHeader />

        {loadError && (
          <div
            className="state-block"
            style={{ color: "var(--danger)" }}
          >
            <div className="state-icon" style={{ color: "var(--danger)" }}>
              <Inbox />
            </div>
            <h3>Не удалось загрузить задачи</h3>
            <p>{String(loadError instanceof Error ? loadError.message : loadError)}</p>
          </div>
        )}

        {!loadError && isLoading && (
          <div
            style={{
              padding: "18px 24px",
              color: "var(--fg-2)",
              fontSize: 12,
            }}
          >
            Загрузка…
          </div>
        )}

        {!loadError && !isLoading && filtered.length === 0 && (
          <div className="state-block">
            <div className="state-icon">
              <Inbox />
            </div>
            <h3>Нет задач</h3>
            <p>
              Навесьте лейбл <span className="mono">agent-task</span> на issue
              в исходном репозитории и запустите <span className="mono">uv run foundry run</span>,
              чтобы Foundry подобрал её в обработку.
            </p>
          </div>
        )}

        {!loadError && !isLoading && filtered.length > 0 && (
          <div>
            {filtered.map((t) => (
              <TaskRow
                key={t.id}
                task={t}
                expanded={expandedId === t.id}
                onToggle={() =>
                  setExpandedId((cur) => (cur === t.id ? null : t.id))
                }
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
