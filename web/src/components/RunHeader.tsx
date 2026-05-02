import type { JSX } from 'react';

import { useRetryRun, useStopRun } from '../api/hooks';
import type { UiAutomation, UiRun } from '../api/types';
import { FAILURE_LABEL, FAILURE_TOOLTIP, STATUS_WORD } from '../lib/status';
import { IconBolt, IconExternal, IconRefresh, IconStop } from './icons';
import { StatusGlyph } from './StatusGlyph';

interface Props {
  run: UiRun;
  automation?: UiAutomation;
  onPickAutomation: (id: string) => void;
}

export function RunHeader({
  run,
  automation,
  onPickAutomation,
}: Props): JSX.Element {
  const stop = useStopRun();
  const retry = useRetryRun();
  const failure = run.failure_kind ? FAILURE_LABEL[run.failure_kind] : null;
  const tooltip = run.failure_kind ? FAILURE_TOOLTIP[run.failure_kind] : '';

  const isTerminal =
    run.status === 'done' ||
    run.status === 'failed' ||
    run.status === 'unclear';

  return (
    <div className="v2-detail-headrow">
      <span className={`v2-status-pill ${run.status}`}>
        <StatusGlyph status={run.status} />
        {STATUS_WORD[run.status]}
      </span>
      <button
        className="v2-aut-pill"
        onClick={() => onPickAutomation(run.automation_id)}
      >
        <IconBolt />
        {automation?.name ?? run.automation_id}
      </button>
      <span className="v2-session-info">
        <span className="session-id">{run.session_id}</span>
        {run.session_seq > 1 && (
          <span className="attempt"> · attempt {run.session_seq}</span>
        )}
      </span>
      {failure && run.failure_kind && (
        <span
          className={`v2-failure-pill ${run.failure_kind}`}
          title={tooltip}
        >
          {failure}
        </span>
      )}
      <span style={{ flex: 1 }}></span>
      <button
        className="topbar-btn"
        disabled={!isTerminal || retry.isPending}
        onClick={() => retry.mutate(run.id)}
        title={isTerminal ? 'Создать новый attempt' : 'Run не завершён'}
      >
        <IconRefresh className="ico-sm" /> retry
      </button>
      {!isTerminal && (
        <button
          className="topbar-btn"
          disabled={stop.isPending}
          onClick={() => stop.mutate(run.id)}
          title="Остановить run"
        >
          <IconStop className="ico-sm" /> stop
        </button>
      )}
      {run.trigger?.source === 'github_issues' && (
        <a
          className="topbar-btn"
          href="#"
          onClick={(e) => e.preventDefault()}
          title="Открыть источник (UI-stub)"
        >
          <IconExternal className="ico-sm" /> open source
        </a>
      )}
    </div>
  );
}
