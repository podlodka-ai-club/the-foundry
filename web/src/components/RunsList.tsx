import type { JSX } from 'react';

import {
  useAutomationRuns,
  useAutomations,
} from '../api/hooks';
import { groupBySession } from '../lib/format';
import { IconBolt, IconChevLeft } from './icons';
import { SessionRow } from './SessionRow';

interface Props {
  automationId: string;
  activeRunId: number | null;
  onSelectRun: (runId: number) => void;
  onBack: () => void;
}

export function RunsList({
  automationId,
  activeRunId,
  onSelectRun,
  onBack,
}: Props): JSX.Element {
  const { data: automations } = useAutomations();
  const { data: runs, isLoading } = useAutomationRuns(automationId);
  const automation = automations?.find((a) => a.id === automationId);
  // Group runs by session — one row per session, click opens the whole
  // session feed in the right pane.
  const groups = groupBySession(runs ?? []);
  const running = automation?.counts.running ?? 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="v2-runs-head">
        <div className="v2-runs-head-top">
          <button className="v2-runs-back" onClick={onBack}>
            <IconChevLeft style={{ width: 11, height: 11 }} /> automations
          </button>
        </div>
        <div className="v2-runs-head-top">
          <IconBolt style={{ width: 14, height: 14, color: 'var(--fg-2)' }} />
          <span
            className="v2-runs-title"
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {automation?.name ?? automationId}
          </span>
        </div>
        <div className="v2-runs-counts">
          {running > 0 && (
            <>
              <b style={{ color: 'var(--running)' }}>{running} running</b> ·{' '}
            </>
          )}
          <b>{automation?.counts.total ?? groups.length}</b> total
        </div>
      </div>
      <div className="v2-runs-list">
        {isLoading && <div className="v2-pane-info">Загрузка…</div>}
        {!isLoading && groups.length === 0 && (
          <div className="v2-pane-info">Нет runs</div>
        )}
        {groups.map((g) => (
          <SessionRow
            key={g.session_id}
            group={g}
            active={g.runs.some((r) => r.id === activeRunId)}
            onClick={() => onSelectRun(g.latest.id)}
          />
        ))}
      </div>
    </div>
  );
}
