import type { JSX } from 'react';

import type { UiAutomation, UiRun } from '../api/types';
import {
  fmtCost,
  fmtDuration,
  fmtRelativeTime,
  pluralRu,
  type SessionGroup,
} from '../lib/format';
import { outcomeLabel, outcomeTone } from '../lib/outcome';
import { STATUS_WORD } from '../lib/status';
import { IconBolt } from './icons';
import { StatusGlyph } from './StatusGlyph';

interface Props {
  group: SessionGroup<UiRun>;
  active: boolean;
  onClick: () => void;
  inbox?: boolean;
  automation?: UiAutomation;
}

function isChat(source: string | undefined): boolean {
  return source === 'telegram' || source === 'discord';
}

function shortRepo(full: string | null | undefined): string | null {
  if (!full) return null;
  const slash = full.lastIndexOf('/');
  return slash >= 0 ? full.slice(slash + 1) : full;
}

function pluralForGroup(n: number, source: string | undefined): string {
  if (isChat(source)) {
    return pluralRu(n, ['сообщение', 'сообщения', 'сообщений']);
  }
  return pluralRu(n, ['попытка', 'попытки', 'попыток']);
}

export function SessionRow({
  group,
  active,
  onClick,
  inbox,
  automation,
}: Props): JSX.Element {
  const { runs, latest } = group;
  const trigger = latest.trigger;
  const isMulti = runs.length > 1;
  const chat = isChat(trigger?.source);

  return (
    <div
      className={`v2-run-row v2-session-row ${active ? 'active' : ''} ${inbox ? 'v2-inbox-row' : ''} ${isMulti ? 'multi' : ''}`}
      onClick={onClick}
    >
      <StatusGlyph status={latest.status} />
      {inbox && (
        <span className="v2-inbox-aut">
          <IconBolt />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {automation?.name ?? latest.automation_id}
          </span>
        </span>
      )}
      <div className="v2-run-meta">
        <div className="v2-run-title">
          {chat ? (
            <>
              {trigger?.author && (
                <span className="v2-run-event v2-session-author">
                  {trigger.author}
                </span>
              )}
              {trigger?.short_name && (
                <span className="v2-session-handle">{trigger.short_name}</span>
              )}
              <span className="v2-run-text">{trigger?.text ?? ''}</span>
            </>
          ) : (
            <>
              <span className="v2-run-event">
                {trigger?.short_name ?? trigger?.external_id ?? `event#${latest.event_id}`}
              </span>
              {shortRepo(trigger?.repo) && (
                <span className="v2-run-repo">{shortRepo(trigger?.repo)}</span>
              )}
              <span className="v2-run-text">{trigger?.text ?? ''}</span>
            </>
          )}
        </div>
        <div className="v2-run-sub">
          <span className="src">{trigger?.source ?? '—'}</span>
          {isMulti ? (
            <>
              <span className="dot">·</span>
              <span className="v2-session-count">
                {runs.length} {pluralForGroup(runs.length, trigger?.source)}
              </span>
            </>
          ) : (
            !chat && trigger?.author && (
              <>
                <span className="dot">·</span>
                <span className="author">by {trigger.author}</span>
              </>
            )
          )}
        </div>
      </div>
      <div className="v2-run-trail">
        {latest.status === 'done' && latest.outcome ? (
          <span className={`v2-outcome-pill ${outcomeTone(latest.outcome)}`}>
            {outcomeLabel(latest.outcome)}
          </span>
        ) : (
          <span className={`status-word ${latest.status}`}>
            {latest.status === 'running'
              ? fmtDuration(latest.duration_sec)
              : STATUS_WORD[latest.status]}
          </span>
        )}
        {latest.status !== 'running' && (
          <span>
            {fmtDuration(latest.duration_sec)} · {fmtCost(latest.cost_usd)}
          </span>
        )}
        {latest.finished_at && latest.status !== 'running' && (
          <span className="finished-at">
            {fmtRelativeTime(latest.finished_at)}
          </span>
        )}
      </div>
    </div>
  );
}
