import type { JSX } from 'react';

import { useTriggers } from '../api/hooks';
import { fmtRelativeTime } from '../lib/format';
import { IconWebhook } from './icons';

export function TriggersFooter(): JSX.Element | null {
  const { data } = useTriggers();
  const triggers = data ?? [];
  if (triggers.length === 0) return null;
  const okCount = triggers.filter((t) => t.health === 'ok').length;
  return (
    <div className="v2-triggers">
      <div className="v2-triggers-head">
        <IconWebhook style={{ width: 10, height: 10 }} /> Triggers
        <span style={{ flex: 1 }}></span>
        <span style={{ color: 'var(--fg-3)', fontSize: 10 }}>
          {okCount}/{triggers.length} ok
        </span>
      </div>
      {triggers.map((t) => {
        const cls =
          t.health === 'ok'
            ? 'ok'
            : t.health === 'stale'
              ? 'down'
              : 'waiting';
        return (
          <div key={t.id} className="v2-trig-row">
            <span className={`v2-trig-dot ${cls}`}></span>
            <span className="v2-trig-name">{t.id}</span>
            <span className="v2-trig-seen">{fmtRelativeTime(t.last_seen)}</span>
          </div>
        );
      })}
    </div>
  );
}
