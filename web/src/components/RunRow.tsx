import type { JSX } from 'react';

import type { UiAutomation, UiRun } from '../api/types';
import { fmtCost, fmtDuration } from '../lib/format';
import { STATUS_WORD } from '../lib/status';
import { IconBolt } from './icons';
import { StatusGlyph } from './StatusGlyph';

interface Props {
  run: UiRun;
  active: boolean;
  onClick: () => void;
  inbox?: boolean;
  automation?: UiAutomation;
}

export function RunRow({
  run,
  active,
  onClick,
  inbox,
  automation,
}: Props): JSX.Element {
  const trigger = run.trigger;
  return (
    <div
      className={`v2-run-row ${active ? 'active' : ''} ${inbox ? 'v2-inbox-row' : ''}`}
      onClick={onClick}
    >
      <StatusGlyph status={run.status} />
      {inbox && (
        <span className="v2-inbox-aut">
          <IconBolt />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {automation?.name ?? run.automation_id}
          </span>
        </span>
      )}
      <div className="v2-run-meta">
        <div className="v2-run-title">
          <span className="v2-run-event">
            {trigger?.external_id ?? `event#${run.event_id}`}
          </span>
          {run.session_seq > 1 && (
            <span className="v2-attempt-badge">attempt {run.session_seq}</span>
          )}
          <span className="v2-run-text">{trigger?.text ?? ''}</span>
        </div>
        <div className="v2-run-sub">
          <span className="src">{trigger?.source ?? '—'}</span>
          {trigger?.author && (
            <>
              <span className="dot">·</span>
              <span className="author">by {trigger.author}</span>
            </>
          )}
        </div>
      </div>
      <div className="v2-run-trail">
        <span className={`status-word ${run.status}`}>
          {run.status === 'running'
            ? fmtDuration(run.duration_sec)
            : STATUS_WORD[run.status]}
        </span>
        {run.status !== 'running' && (
          <span>
            {fmtDuration(run.duration_sec)} · {fmtCost(run.cost_usd)}
          </span>
        )}
      </div>
    </div>
  );
}
