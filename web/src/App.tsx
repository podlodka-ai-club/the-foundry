import type { JSX } from 'react';
import { useState } from 'react';

import type { RunsFilter } from './api/types';
import { RunDetail } from './components/RunDetail';
import { Sidebar } from './components/Sidebar';
import type { SidebarTab } from './components/Sidebar';

export default function App(): JSX.Element {
  const [tab, setTab] = useState<SidebarTab>('automations');
  const [automationId, setAutomationId] = useState<string | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [inboxFilter, setInboxFilter] = useState<RunsFilter>('all');

  const handlePickAutomation = (id: string): void => {
    setAutomationId(id);
    setTab('runs');
    setRunId(null);
  };

  return (
    <div className="v2-shell">
      <Sidebar
        tab={tab}
        setTab={setTab}
        automationId={automationId}
        setAutomationId={setAutomationId}
        runId={runId}
        setRunId={setRunId}
        inboxFilter={inboxFilter}
        setInboxFilter={setInboxFilter}
      />
      <RunDetail runId={runId} onPickAutomation={handlePickAutomation} onSelectRun={setRunId} />
    </div>
  );
}
