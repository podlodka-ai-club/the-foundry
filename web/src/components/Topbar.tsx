import type { JSX } from "react";
import { useState } from "react";
import { Play, Search, RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { triggerFetch } from "../api";

interface TopbarProps {
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
}

export default function Topbar({
  searchQuery,
  onSearchQueryChange,
}: TopbarProps): JSX.Element {
  const queryClient = useQueryClient();
  const [pulling, setPulling] = useState(false);
  const [pullResult, setPullResult] = useState<string | null>(null);

  async function handlePull() {
    setPulling(true);
    setPullResult(null);
    try {
      const { fetched } = await triggerFetch();
      setPullResult(`+${fetched}`);
      await queryClient.invalidateQueries({ queryKey: ["tasks"] });
      await queryClient.invalidateQueries({ queryKey: ["repos"] });
    } catch {
      setPullResult("err");
    } finally {
      setPulling(false);
      setTimeout(() => setPullResult(null), 3000);
    }
  }

  return (
    <div className="topbar">
      <span className="topbar-title">Задачи</span>
      <span className="topbar-crumb">· все репозитории</span>

      <span className="topbar-spacer" />

      <div className="search">
        <Search />
        <input
          value={searchQuery}
          onChange={(event) => onSearchQueryChange(event.currentTarget.value)}
          placeholder="Поиск по задачам…"
        />
      </div>

      <button
        className="topbar-btn"
        onClick={handlePull}
        disabled={pulling}
        title="Подтянуть задачи из GitHub"
        style={{ minWidth: 90 }}
      >
        <RefreshCw style={{ animation: pulling ? "spinner .8s linear infinite" : undefined }} />
        {pullResult !== null ? pullResult : pulling ? "…" : "Pull"}
      </button>

      <button
        className="topbar-btn primary"
        disabled
        title="Запуск из UI появится позже — пока используйте uv run foundry run"
        style={{ opacity: 0.6, cursor: "not-allowed" }}
      >
        <Play />
        Run
      </button>
    </div>
  );
}
