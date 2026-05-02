import type { JSX } from 'react';

import { useAutomations, useRuns } from '../api/hooks';
import type { RunsFilter } from '../api/types';
import { IconInbox } from './icons';
import { RunRow } from './RunRow';

interface Props {
  filter: RunsFilter;
  setFilter: (f: RunsFilter) => void;
  activeRunId: number | null;
  onSelectRun: (runId: number) => void;
}

const FILTERS: RunsFilter[] = ['all', 'running', 'waiting', 'failed'];

export function InboxList({
  filter,
  setFilter,
  activeRunId,
  onSelectRun,
}: Props): JSX.Element {
  const { data: runs, isLoading } = useRuns(filter);
  const { data: automations } = useAutomations();

  const all = runs ?? [];
  const counts = {
    running: all.filter((r) => r.status === 'running').length,
    waiting: all.filter((r) => r.status === 'waiting').length,
    failed: all.filter(
      (r) => r.status === 'failed' || r.status === 'unclear',
    ).length,
    all: all.length,
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="v2-runs-head">
        <div className="v2-runs-head-top">
          <IconInbox style={{ width: 14, height: 14, color: 'var(--fg-2)' }} />
          <span className="v2-runs-title">All runs</span>
        </div>
        <div className="v2-runs-counts">
          across {automations?.length ?? 0} automations
        </div>
      </div>
      <div className="v2-filter-bar">
        {FILTERS.map((f) => (
          <button
            key={f}
            className={`v2-filter ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)}
          >
            {f === 'running' && (
              <span
                className="v2-glyph running"
                style={{ width: 8, height: 8 }}
              ></span>
            )}
            {f}
            <span className="v2-filter-count">{counts[f]}</span>
          </button>
        ))}
      </div>
      <div className="v2-runs-list">
        {isLoading && <div className="v2-pane-info">Загрузка…</div>}
        {!isLoading && all.length === 0 && (
          <div className="v2-pane-info">Нет runs</div>
        )}
        {all.map((r) => {
          const aut = automations?.find((a) => a.id === r.automation_id);
          return (
            <RunRow
              key={r.id}
              run={r}
              active={activeRunId === r.id}
              onClick={() => onSelectRun(r.id)}
              inbox
              automation={aut}
            />
          );
        })}
      </div>
    </div>
  );
}
