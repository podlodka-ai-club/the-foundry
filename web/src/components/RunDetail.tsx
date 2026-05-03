import type { JSX } from 'react';
import { useMemo } from 'react';

import {
  useAutomationRuns,
  useAutomations,
  useRetryRun,
  useRun,
  useRuns_byIds,
  useStopRun,
} from '../api/hooks';
import { useRunStream } from '../api/sse';
import type { UiRunDetail } from '../api/types';
import { mergeBySeq, treeFromEvents } from '../lib/eventTree';
import { STATUS_WORD } from '../lib/status';
import { Composer } from './Composer';
import { EmptyDetail } from './EmptyDetail';
import { IconBolt, IconExternal, IconRefresh, IconStop } from './icons';
import { InputZone } from './zones/InputZone';
import { OutputZone } from './zones/OutputZone';
import { ProcessZone } from './zones/ProcessZone';

interface Props {
  runId: number | null;
  onPickAutomation: (id: string) => void;
  onSelectRun: (runId: number) => void;
}

function isChat(source: string | undefined): boolean {
  return source === 'telegram' || source === 'discord';
}

export function RunDetail({
  runId,
  onPickAutomation,
}: Props): JSX.Element {
  const { data: focused } = useRun(runId);
  const { data: automations } = useAutomations();
  const { events: liveEvents } = useRunStream(runId);
  const { data: siblingRuns } = useAutomationRuns(focused?.automation_id ?? null);
  const stop = useStopRun();
  const retry = useRetryRun();

  // All runs of the focused session, oldest → newest. Click on any session
  // in the sidebar focuses its latest run, so this gives the full thread.
  const sessionRuns = useMemo(() => {
    if (!focused) return [];
    return (siblingRuns ?? [])
      .filter((r) => r.session_id === focused.session_id)
      .sort((a, b) => a.session_seq - b.session_seq || a.id - b.id);
  }, [focused, siblingRuns]);

  // Fetch full detail (including events) for each sibling so we can render
  // their Process/Output zones too. The focused run reuses its query result,
  // and React Query dedupes by ['run', id].
  const siblingIds = useMemo(
    () => sessionRuns.map((r) => r.id).filter((id) => id !== focused?.id),
    [sessionRuns, focused],
  );
  const siblingQueries = useRuns_byIds(siblingIds);
  const siblingDetails = useMemo(() => {
    const m = new Map<number, UiRunDetail>();
    for (const q of siblingQueries) {
      if (q.data) m.set(q.data.id, q.data);
    }
    return m;
  }, [siblingQueries]);

  if (runId === null || !focused) {
    return <EmptyDetail />;
  }

  const automation = automations?.find((a) => a.id === focused.automation_id);
  const lastRun = sessionRuns[sessionRuns.length - 1] ?? focused;
  const isTerminal =
    lastRun.status === 'done' ||
    lastRun.status === 'failed' ||
    lastRun.status === 'unclear';
  const chatHeader = isChat(focused.trigger?.source);

  return (
    <div className="v2-detail v3-detail">
      <div className="v3-detail-head">
        <span className={`v3-pill ${lastRun.status}`}>
          <span className={`v3-pill-dot ${lastRun.status}`}></span>
          {STATUS_WORD[lastRun.status]}
        </span>
        <button
          className="v2-aut-pill"
          onClick={() => onPickAutomation(focused.automation_id)}
        >
          <IconBolt />
          {automation?.name ?? focused.automation_id}
        </button>
        {chatHeader && focused.trigger?.author && (
          <span className="v3-session-author">
            <span className="v3-session-author-name">
              {focused.trigger.author}
            </span>
            {focused.trigger.short_name && (
              <span className="v3-session-author-handle">
                {focused.trigger.short_name}
              </span>
            )}
          </span>
        )}
        <span style={{ flex: 1 }} />
        {!isTerminal ? (
          <button
            className="topbar-btn"
            disabled={stop.isPending}
            onClick={() => stop.mutate(lastRun.id)}
          >
            <IconStop className="ico-sm" /> stop
          </button>
        ) : (
          <button
            className="topbar-btn"
            disabled={retry.isPending}
            onClick={() => retry.mutate(lastRun.id)}
          >
            <IconRefresh className="ico-sm" /> retry
          </button>
        )}
        {focused.trigger?.source.startsWith('github') && (
          <a
            className="topbar-btn"
            href="#"
            onClick={(e) => e.preventDefault()}
          >
            <IconExternal className="ico-sm" /> open source
          </a>
        )}
      </div>

      <div className="v3-body v3-feed">
        {sessionRuns.map((r, i) => {
          // For the focused run: merge live SSE events on top of detail.
          // For siblings: their full detail comes from useRuns_byIds.
          let events = r.id === focused.id ? focused.events : [];
          if (r.id === focused.id) {
            events = mergeBySeq(focused.events, liveEvents);
          } else {
            const detail = siblingDetails.get(r.id);
            if (detail) events = detail.events;
          }
          const tree = treeFromEvents(events);
          const subagents = events.filter((e) =>
            e.stage.startsWith('subagent:'),
          ).length;
          return (
            <div
              key={r.id}
              className={`v3-turn ${i === sessionRuns.length - 1 ? 'is-last' : ''}`}
            >
              <InputZone run={r} />
              <ProcessZone
                run={r}
                tree={tree}
                subagentCount={subagents}
              />
              <OutputZone
                run={r}
                automation={automation}
                events={events}
              />
            </div>
          );
        })}
      </div>

      <Composer run={lastRun} />
    </div>
  );
}
