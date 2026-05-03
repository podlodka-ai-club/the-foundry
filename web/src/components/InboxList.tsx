import type { JSX } from 'react';

import { useAutomations, useRuns } from '../api/hooks';
import type { RunsFilter } from '../api/types';
import { groupBySession } from '../lib/format';
import { IconInbox } from './icons';
import { SessionRow } from './SessionRow';

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

  const groups = groupBySession(runs ?? []);
  const counts = {
    running: groups.filter((g) => g.latest.status === 'running').length,
    waiting: groups.filter((g) => g.latest.status === 'waiting').length,
    failed: groups.filter(
      (g) => g.latest.status === 'failed' || g.latest.status === 'unclear',
    ).length,
    all: groups.length,
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
        {!isLoading && groups.length === 0 && (
          <div className="v2-pane-info">Нет runs</div>
        )}
        {groups.map((g) => {
          const aut = automations?.find((a) => a.id === g.latest.automation_id);
          return (
            <SessionRow
              key={g.session_id}
              group={g}
              active={g.runs.some((r) => r.id === activeRunId)}
              onClick={() => onSelectRun(g.latest.id)}
              inbox
              automation={aut}
            />
          );
        })}
      </div>
    </div>
  );
}
