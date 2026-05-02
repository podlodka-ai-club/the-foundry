// automations-v2-app.jsx — design canvas с артбордами для v2

function AppV2() {
  return (
    <DesignCanvas storageKey="orchestrator-automations-v2" defaultZoom={0.65}>
      <DCSection
        id="states"
        title="Foundry · Automations · v2"
        subtitle="Variant B + claude.app визуальный язык. Routine-style automations list, одна моноцветная иконка статуса, attempt-badge вместо session-line, mark_milestone как разделитель внутри дерева."
      >
        <DCArtboard id="dev-running" label="dev_task RUNNING — sub-agents+mark_milestone" width={1440} height={820}>
          <div data-screen-label="V2 · dev_task RUNNING" style={{ width: 1440, height: 820, background: 'var(--bg-0)' }}>
            <AutomationsV2 defaultTab="runs" defaultAut="dev_task" defaultRun="run_e84a" />
          </div>
        </DCArtboard>

        <DCArtboard id="pr-done" label="pr_reviewer DONE — короткое дерево, без sub-agents" width={1440} height={820}>
          <div data-screen-label="V2 · pr_reviewer DONE" style={{ width: 1440, height: 820, background: 'var(--bg-0)' }}>
            <AutomationsV2 defaultTab="runs" defaultAut="pr_reviewer" defaultRun="run_b612" />
          </div>
        </DCArtboard>

        <DCArtboard id="intent-waiting" label="intent_to_task WAITING_HUMAN — composer ‘ответьте’" width={1440} height={820}>
          <div data-screen-label="V2 · intent_to_task WAITING" style={{ width: 1440, height: 820, background: 'var(--bg-0)' }}>
            <AutomationsV2 defaultTab="runs" defaultAut="intent_to_task" defaultRun="run_d802" />
          </div>
        </DCArtboard>

        <DCArtboard id="dev-failed" label="dev_task FAILED — failure_kind «Тесты/lint», attempt 2" width={1440} height={820}>
          <div data-screen-label="V2 · dev_task FAILED" style={{ width: 1440, height: 820, background: 'var(--bg-0)' }}>
            <AutomationsV2 defaultTab="runs" defaultAut="dev_task" defaultRun="run_a93c" />
          </div>
        </DCArtboard>

        <DCArtboard id="inbox-running" label="Inbox tab · фильтр RUNNING" width={1440} height={820}>
          <div data-screen-label="V2 · Inbox running" style={{ width: 1440, height: 820, background: 'var(--bg-0)' }}>
            <AutomationsV2 defaultTab="inbox" defaultRun="run_c401" inboxFilter="running" />
          </div>
        </DCArtboard>

        <DCArtboard id="empty" label="Automations tab · пустой Run Detail справа" width={1440} height={820}>
          <div data-screen-label="V2 · empty detail" style={{ width: 1440, height: 820, background: 'var(--bg-0)' }}>
            <AutomationsV2 defaultTab="automations" defaultAut="daily_digest" defaultRun="__none__" />
          </div>
        </DCArtboard>
      </DCSection>
    </DesignCanvas>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<AppV2 />);
