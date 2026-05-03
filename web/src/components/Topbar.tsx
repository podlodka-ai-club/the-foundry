import type { JSX } from "react";
import { Play, Search } from "lucide-react";

export default function Topbar(): JSX.Element {
  return (
    <div className="topbar">
      <span className="topbar-title">Задачи</span>
      <span className="topbar-crumb">· все репозитории</span>

      <span className="topbar-spacer" />

      <div
        className="search"
        aria-disabled="true"
        title="Поиск появится позже"
        style={{ opacity: 0.7, pointerEvents: "none" }}
      >
        <Search />
        <input placeholder="Поиск по задачам…" disabled />
      </div>

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
