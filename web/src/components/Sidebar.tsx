import type { JSX } from 'react';

import { useAutomations, useRuns } from '../api/hooks';
import type { RunsFilter } from '../api/types';
import { AutomationsList } from './AutomationsList';
import { IconBolt, IconBranch, IconInbox } from './icons';
import { InboxList } from './InboxList';
import { RunsList } from './RunsList';

export type SidebarTab = 'automations' | 'runs' | 'inbox';

interface Props {
  tab: SidebarTab;
  setTab: (t: SidebarTab) => void;
  automationId: string | null;
  setAutomationId: (id: string | null) => void;
  runId: number | null;
  setRunId: (id: number | null) => void;
  inboxFilter: RunsFilter;
  setInboxFilter: (f: RunsFilter) => void;
}

export function Sidebar({
  tab,
  setTab,
  automationId,
  setAutomationId,
  runId,
  setRunId,
  inboxFilter,
  setInboxFilter,
}: Props): JSX.Element {
  const { data: automations } = useAutomations();
  const { data: allRuns } = useRuns('all');

  const handlePickAut = (id: string): void => {
    setAutomationId(id);
    setTab('runs');
    setRunId(null);
  };

  return (
    <div className="v2-sidebar">
      <div className="v2-sidebar-tabs">
        <button
          className={`v2-tab ${tab === 'automations' ? 'active' : ''}`}
          onClick={() => setTab('automations')}
        >
          <IconBolt /> automations
          <span className="v2-tab-count">{automations?.length ?? 0}</span>
        </button>
        <button
          className={`v2-tab ${tab === 'runs' ? 'active' : ''}`}
          onClick={() => setTab('runs')}
        >
          <IconBranch /> runs
          <span className="v2-tab-count">
            {automationId
              ? (allRuns ?? []).filter((r) => r.automation_id === automationId).length
              : 0}
          </span>
        </button>
        <button
          className={`v2-tab ${tab === 'inbox' ? 'active' : ''}`}
          onClick={() => setTab('inbox')}
        >
          <IconInbox /> inbox
          <span className="v2-tab-count">{allRuns?.length ?? 0}</span>
        </button>
      </div>

      <div className="v2-pane-body">
        {tab === 'automations' && (
          <AutomationsList
            activeId={automationId}
            onSelect={handlePickAut}
          />
        )}
        {tab === 'runs' && automationId && (
          <RunsList
            automationId={automationId}
            activeRunId={runId}
            onSelectRun={setRunId}
            onBack={() => setTab('automations')}
          />
        )}
        {tab === 'runs' && !automationId && (
          <div className="v2-pane-info">Выберите automation сначала</div>
        )}
        {tab === 'inbox' && (
          <InboxList
            filter={inboxFilter}
            setFilter={setInboxFilter}
            activeRunId={runId}
            onSelectRun={setRunId}
          />
        )}
      </div>
    </div>
  );
}
