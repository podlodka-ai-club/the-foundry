// automations-app.jsx — три варианта в design canvas

function App() {
  return (
    <DesignCanvas storageKey="orchestrator-automations" defaultZoom={0.65}>
      <DCSection id="overview" title="Foundry · Automations Factory" subtitle="Триггеры → Automations → Runs → Tree of calls. Три раскладки одной идеи.">
        <DCArtboard id="classic" label="A · Классические 3 колонки (recommended)" width={1440} height={780}>
          <div data-screen-label="Variant A · Classic 3-column" style={{ width: 1440, height: 780, background: 'var(--bg-0)' }}>
            <VariantClassic defaultRun="run_e84a" defaultAut="dev_task" />
          </div>
        </DCArtboard>

        <DCArtboard id="twopane" label="B · Две панели — больше места дереву" width={1440} height={780}>
          <div data-screen-label="Variant B · Two-pane wide" style={{ width: 1440, height: 780, background: 'var(--bg-0)' }}>
            <VariantTwoPane defaultRun="run_e84a" defaultAut="dev_task" />
          </div>
        </DCArtboard>

        <DCArtboard id="inbox" label="C · Inbox по всем automations" width={1600} height={780}>
          <div data-screen-label="Variant C · Inbox + slide-over" style={{ width: 1600, height: 780, background: 'var(--bg-0)' }}>
            <VariantInbox defaultRun="run_d802" />
          </div>
        </DCArtboard>
      </DCSection>

      <DCSection id="runs-by-state" title="Один и тот же экран в разных состояниях" subtitle="Смотрим Variant A на разных runs — чтобы оценить пустые/полные/ждущие/упавшие состояния.">
        <DCArtboard id="state-running" label="dev_task · RUNNING (с milestones)" width={1440} height={780}>
          <div style={{ width: 1440, height: 780, background: 'var(--bg-0)' }}>
            <VariantClassic defaultRun="run_e84a" defaultAut="dev_task" />
          </div>
        </DCArtboard>

        <DCArtboard id="state-failed" label="dev_task · FAILED (preempted, session #2)" width={1440} height={780}>
          <div style={{ width: 1440, height: 780, background: 'var(--bg-0)' }}>
            <VariantClassic defaultRun="run_a93c" defaultAut="dev_task" />
          </div>
        </DCArtboard>

        <DCArtboard id="state-pr" label="pr_reviewer · быстрый run без milestones" width={1440} height={780}>
          <div style={{ width: 1440, height: 780, background: 'var(--bg-0)' }}>
            <VariantClassic defaultRun="run_b71f" defaultAut="pr_reviewer" />
          </div>
        </DCArtboard>

        <DCArtboard id="state-waiting" label="intent_to_task · WAITING HUMAN" width={1440} height={780}>
          <div style={{ width: 1440, height: 780, background: 'var(--bg-0)' }}>
            <VariantClassic defaultRun="run_d802" defaultAut="intent_to_task" />
          </div>
        </DCArtboard>
      </DCSection>
    </DesignCanvas>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
