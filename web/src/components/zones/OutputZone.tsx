import type { JSX } from 'react';

import type { UiAutomation, UiEvent, UiRun } from '../../api/types';
import { fmtCost, fmtDuration } from '../../lib/format';
import { CollapsibleText } from '../CollapsibleText';
import { Markdownish } from '../Markdownish';
import { IconBranch, IconExternal, IconX } from '../icons';
import { STATUS_WORD } from '../../lib/status';

interface Props {
  run: UiRun;
  automation: UiAutomation | undefined;
  events: UiEvent[];
}

interface AgentResult {
  text: string;
  pr_url: string | null;
}

const PR_URL_RE = /https?:\/\/github\.com\/[^\s)]+\/pull\/\d+/;

function pickAgentResult(events: UiEvent[]): AgentResult | null {
  // Walk newest first, take the most recent agent_result event.
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (!ev) continue;
    if (ev.kind !== 'agent_result') continue;
    const p = ev.payload;
    const text =
      (typeof p['text'] === 'string' && p['text']) ||
      (typeof p['summary'] === 'string' && p['summary']) ||
      (typeof p['content'] === 'string' && p['content']) ||
      '';
    let url = typeof p['pr_url'] === 'string' ? p['pr_url'] : null;
    if (!url) {
      const m = text.match(PR_URL_RE);
      if (m) url = m[0];
    }
    return { text, pr_url: url };
  }
  return null;
}

function isChatSource(source: string | undefined): boolean {
  return source === 'telegram' || source === 'discord';
}

function StatusPill({ status }: { status: UiRun['status'] }): JSX.Element {
  return (
    <span className={`v3-pill ${status}`}>
      <span className={`v3-pill-dot ${status}`}></span>
      {STATUS_WORD[status]}
    </span>
  );
}

function StatsRow({
  run,
  automation,
  subagentCount,
}: {
  run: UiRun;
  automation: UiAutomation | undefined;
  subagentCount: number;
}): JSX.Element {
  const model =
    automation && typeof automation.agent['model'] === 'string'
      ? (automation.agent['model'] as string)
      : null;
  return (
    <span className="v3-output-stats">
      <span>
        <b>{fmtDuration(run.duration_sec)}</b>
      </span>
      <span className="dot">·</span>
      <span>{fmtCost(run.cost_usd)}</span>
      {model && (
        <>
          <span className="dot">·</span>
          <span className="mono">{model}</span>
        </>
      )}
      {subagentCount > 0 && (
        <>
          <span className="dot">·</span>
          <span>{subagentCount} sub-agent</span>
        </>
      )}
    </span>
  );
}

export function OutputZone({ run, automation, events }: Props): JSX.Element {
  const result = pickAgentResult(events);
  const subagentCount = events.filter((e) =>
    e.stage.startsWith('subagent:'),
  ).length;
  const status = run.status;
  const isFailed = status === 'failed';
  const isWaiting = status === 'waiting';
  const isRunning = status === 'running' || status === 'pending';
  const isUnclear = status === 'unclear';
  const source = run.trigger?.source;

  const Header = (
    <div className="v3-output-head">
      <StatusPill status={status} />
      <StatsRow
        run={run}
        automation={automation}
        subagentCount={subagentCount}
      />
    </div>
  );

  const UnclearNote = isUnclear ? (
    <div className="v3-unclear-note">
      агент закончил, но не вызвал <code>mark_done</code> / <code>mark_failed</code> — статус автоматически выставлен как unclear
    </div>
  ) : null;

  if (isRunning && !result) {
    return (
      <section className="v3-zone v3-zone-output">
        <div className="v3-zone-label">Выход · в процессе</div>
        {Header}
        <div className="v3-output-running">
          <span className="live-caret"></span>
          <span>агент работает — финальный ответ появится когда process завершится</span>
        </div>
      </section>
    );
  }

  if (isFailed) {
    return (
      <section className="v3-zone v3-zone-output v3-output-failed">
        <div className="v3-zone-label">Выход · failed</div>
        {Header}
        <div className="v3-fail-block">
          <div className="v3-fail-head">
            <IconX style={{ width: 12, height: 12 }} />
            <span>{run.failure_msg ?? 'Ошибка без описания'}</span>
          </div>
          {result?.text && <div className="v3-fail-text">{result.text}</div>}
        </div>
      </section>
    );
  }

  if (isWaiting) {
    return (
      <section className="v3-zone v3-zone-output v3-output-waiting">
        <div className="v3-zone-label">Выход · ждём ответа</div>
        {Header}
        {run.waiting_reason && (
          <div className="v3-wait-banner">{run.waiting_reason}</div>
        )}
        {result?.text && (
          <div className="v3-result-card">
            <Markdownish text={result.text} />
          </div>
        )}
      </section>
    );
  }

  if (isChatSource(source) && result?.text) {
    return (
      <section className="v3-zone v3-zone-output v3-tg-out">
        <div className="v3-zone-label">Выход · ответ</div>
        {Header}
        <div className="v3-tg-row right">
          <div className="v3-tg-bubble out">
            <CollapsibleText text={result.text} threshold={6} />
            <div className="v3-tg-bubble-foot out">
              <span>delivered</span>
              <span className="dot">·</span>
              <span>{fmtDuration(run.duration_sec)}</span>
            </div>
          </div>
        </div>
      </section>
    );
  }

  if (result?.pr_url) {
    return (
      <section className="v3-zone v3-zone-output">
        <div className="v3-zone-label">Выход · pull request</div>
        {Header}
        <article className="v3-pr-card">
          <header className="v3-pr-head">
            <span className="v3-pr-status">
              <span className="v3-pr-dot open"></span>
              open
            </span>
            <a
              className="v3-pr-link mono"
              href={result.pr_url}
              target="_blank"
              rel="noreferrer"
            >
              {result.pr_url}
              <IconExternal style={{ width: 10, height: 10 }} />
            </a>
          </header>
          {UnclearNote}
          {result.text && (
            <div className="v3-result-card v3-result-card-inset">
              <Markdownish text={result.text} />
            </div>
          )}
        </article>
      </section>
    );
  }

  if (result?.text) {
    return (
      <section className="v3-zone v3-zone-output">
        <div className="v3-zone-label">Выход · ответ</div>
        {Header}
        {UnclearNote}
        <div className="v3-result-card">
          <Markdownish text={result.text} />
        </div>
      </section>
    );
  }

  // Done but no result text — generic placeholder.
  return (
    <section className="v3-zone v3-zone-output">
      <div className="v3-zone-label">Выход</div>
      {Header}
      <div className="v3-output-running">
        <span>агент завершил работу без явного результата</span>
        {automation?.id === 'dev_task' && (
          <span className="v3-pr-pending">
            <IconBranch />
            <span>PR будет открыт после verify</span>
          </span>
        )}
      </div>
    </section>
  );
}
