import type { JSX } from 'react';
import { useMemo } from 'react';

import { useAutomations, useRun } from '../api/hooks';
import { useRunStream } from '../api/sse';
import { classifyNode, mergeBySeq, treeFromEvents } from '../lib/eventTree';
import { Composer } from './Composer';
import { EmptyDetail } from './EmptyDetail';
import { EventTree } from './EventTree';
import { RunHeader } from './RunHeader';
import { RunStats } from './RunStats';
import { SourceCard } from './SourceCard';
import { SubagentMinimap } from './SubagentMinimap';

interface Props {
  runId: number | null;
  onPickAutomation: (id: string) => void;
}

export function RunDetail({ runId, onPickAutomation }: Props): JSX.Element {
  const { data: detail } = useRun(runId);
  const { data: automations } = useAutomations();
  const { events: liveEvents } = useRunStream(runId);

  const allEvents = useMemo(
    () => mergeBySeq(detail?.events ?? [], liveEvents),
    [detail, liveEvents],
  );
  const tree = useMemo(() => treeFromEvents(allEvents), [allEvents]);

  if (runId === null || !detail) {
    return <EmptyDetail />;
  }

  const automation = automations?.find((a) => a.id === detail.automation_id);
  const subCount = tree.filter((n) => classifyNode(n.event) === 'subagent').length;

  return (
    <div className="v2-detail">
      <div className="v2-detail-head">
        <RunHeader
          run={detail}
          automation={automation}
          onPickAutomation={onPickAutomation}
        />
        <SourceCard trigger={detail.trigger} />
        <RunStats
          run={detail}
          automation={automation}
          subagentCount={subCount}
        />
      </div>

      <SubagentMinimap roots={tree} />

      <div className="v2-tree-wrap">
        {tree.length === 0 && (
          <div className="v2-pane-info">Событий пока нет</div>
        )}
        <EventTree nodes={tree} />
      </div>

      <Composer run={detail} />
    </div>
  );
}
