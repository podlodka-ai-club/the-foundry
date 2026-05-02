import type { JSX } from 'react';

import type { UiAutomation, UiRun } from '../api/types';
import { fmtCost, fmtDuration } from '../lib/format';

interface Props {
  run: UiRun;
  automation?: UiAutomation;
  subagentCount: number;
}

export function RunStats({ run, automation, subagentCount }: Props): JSX.Element {
  const model = (automation?.agent['model'] as string | undefined) ?? '—';
  return (
    <div className="v2-detail-stats">
      <span><b>{model}</b></span>
      <span className="sep">·</span>
      <span>
        длительность <b>{fmtDuration(run.duration_sec)}</b>
        {run.status === 'running' && <span className="live-caret"></span>}
      </span>
      <span className="sep">·</span>
      <span>стоимость <b>{fmtCost(run.cost_usd)}</b></span>
      {subagentCount > 0 && (
        <>
          <span className="sep">·</span>
          <span><b>{subagentCount}</b> sub-agent calls</span>
        </>
      )}
      {run.failure_msg && (
        <>
          <span className="sep">·</span>
          <span style={{ color: 'var(--danger)' }}>{run.failure_msg}</span>
        </>
      )}
      {run.waiting_reason && (
        <>
          <span className="sep">·</span>
          <span style={{ color: 'var(--highlight)' }}>{run.waiting_reason}</span>
        </>
      )}
    </div>
  );
}
