import type { JSX } from 'react';

import type { UiRun } from '../../api/types';
import { CollapsibleText } from '../CollapsibleText';
import { IconClock, IconGitHub } from '../icons';

interface Props {
  run: UiRun;
}

function isChatSource(source: string): boolean {
  return source === 'telegram' || source === 'discord';
}

function isGitHubSource(source: string): boolean {
  return source.startsWith('github');
}

function isCronSource(source: string): boolean {
  return source === 'cron';
}

export function InputZone({ run }: Props): JSX.Element | null {
  const trigger = run.trigger;
  if (!trigger) return null;
  const { source, text, author, short_name, external_id } = trigger;

  if (isChatSource(source)) {
    return (
      <section className="v3-zone v3-zone-input v3-tg-in">
        <div className="v3-zone-label">Вход · сообщение</div>
        <div className="v3-tg-row">
          <div className="v3-tg-bubble in">
            {(author || short_name) && (
              <div className="v3-tg-bubble-head">
                {author && <span className="v3-tg-author">{author}</span>}
                {short_name && <span className="v3-tg-handle">{short_name}</span>}
              </div>
            )}
            <CollapsibleText text={text} threshold={2} charLimit={140} />
            <div className="v3-tg-bubble-foot">
              <span className="mono">{external_id}</span>
              <span className="dot">·</span>
              <span>{run.started_at}</span>
            </div>
          </div>
        </div>
      </section>
    );
  }

  if (isGitHubSource(source)) {
    const isPr = trigger.kind.startsWith('pr.');
    return (
      <section className="v3-zone v3-zone-input">
        <div className="v3-zone-label">
          Вход · {isPr ? 'pull request' : 'issue'}
        </div>
        <article className="v3-issue-card">
          <header className="v3-issue-head">
            <IconGitHub />
            <span className="v3-issue-num mono">
              {short_name ?? external_id}
            </span>
            <span className="v3-issue-repo mono">{source}</span>
            <span className="v3-issue-spacer" />
            {author && (
              <span className="v3-issue-author">
                opened by <b>{author}</b>
              </span>
            )}
          </header>
          <h3 className="v3-issue-title">{text || external_id}</h3>
        </article>
      </section>
    );
  }

  if (isCronSource(source)) {
    return (
      <section className="v3-zone v3-zone-input">
        <div className="v3-zone-label">Вход · cron</div>
        <article className="v3-cron-card">
          <IconClock />
          <div style={{ minWidth: 0 }}>
            <div className="v3-cron-rule mono">
              {short_name ?? text ?? external_id}
            </div>
            <div className="v3-cron-meta">
              <span>{source}</span>
              <span className="dot">·</span>
              <span>fired {run.started_at}</span>
            </div>
          </div>
        </article>
      </section>
    );
  }

  // Generic fallback — render as a neutral source card.
  return (
    <section className="v3-zone v3-zone-input">
      <div className="v3-zone-label">Вход · {source}</div>
      <article className="v3-cron-card">
        <div style={{ minWidth: 0 }}>
          <div className="v3-cron-rule">{text || external_id}</div>
          <div className="v3-cron-meta">
            <span className="mono">{short_name ?? external_id}</span>
            {author && (
              <>
                <span className="dot">·</span>
                <span>by {author}</span>
              </>
            )}
          </div>
        </div>
      </article>
    </section>
  );
}
