import type { JSX } from 'react';

import type { UiRunTrigger } from '../api/types';
import { triggerKindIcon } from './icons';

interface Props {
  trigger: UiRunTrigger | null;
}

export function SourceCard({ trigger }: Props): JSX.Element | null {
  if (!trigger) return null;
  const Icon = triggerKindIcon(trigger.kind);
  return (
    <div className="v2-source-card">
      <div className="v2-source-meta">
        <Icon />
        <span className="src">{trigger.source}</span>
        <span className="dot">·</span>
        <span style={{ fontFamily: 'var(--font-mono)' }}>
          {trigger.external_id}
        </span>
        {trigger.author && (
          <>
            <span className="dot">·</span>
            <span>by {trigger.author}</span>
          </>
        )}
      </div>
      <div>{trigger.text}</div>
    </div>
  );
}
