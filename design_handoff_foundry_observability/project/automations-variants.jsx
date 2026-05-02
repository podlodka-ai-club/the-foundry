// automations-variants.jsx — три раскладки одной идеи в design canvas

// ─── Variant A: Classic 3-column (280 / 380 / 1fr) ────────────
function VariantClassic({ defaultRun = 'run_e84a', defaultAut = 'dev_task' }) {
  const [aut, setAut] = React.useState(defaultAut);
  const [run, setRun] = React.useState(defaultRun);

  // При переключении automation сбросим выбор run на первый видимый
  const onPickAut = (id) => {
    setAut(id);
    const first = RUNS.find(r => r.automation === id);
    setRun(first?.id);
  };

  return (
    <div className="automations-shell" style={{ height: 720 }}>
      <AutomationsCol activeId={aut} onSelect={onPickAut} />
      <RunsCol automationId={aut} activeRunId={run} onSelect={setRun} />
      <RunDetail runId={run} />
    </div>
  );
}

// ─── Variant B: Two-pane wide (350 / 1fr) ──────────────────────
// Левая панель = automations + runs одной выбранной (через табы),
// правая колонка широкая — больше места дереву.
function VariantTwoPane({ defaultRun = 'run_e84a', defaultAut = 'dev_task' }) {
  const [aut, setAut] = React.useState(defaultAut);
  const [run, setRun] = React.useState(defaultRun);
  const [tab, setTab] = React.useState('runs'); // 'runs' | 'automations'
  const onPickAut = (id) => {
    setAut(id);
    setTab('runs');
    const first = RUNS.find(r => r.automation === id);
    setRun(first?.id);
  };

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '360px 1fr',
      height: 720,
      background: 'var(--bg-0)',
    }}>
      {/* Combined left pane */}
      <div style={{
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        background: 'var(--bg-1)',
        minHeight: 0,
      }}>
        {/* Pane header with tabs */}
        <div style={{ borderBottom: '1px solid var(--border)', display: 'flex' }}>
          <button
            onClick={() => setTab('automations')}
            style={{
              flex: 1, padding: '11px 12px',
              background: tab === 'automations' ? 'var(--bg-1)' : 'transparent',
              border: 'none', borderBottom: tab === 'automations' ? '2px solid var(--accent)' : '2px solid transparent',
              color: tab === 'automations' ? 'var(--fg-0)' : 'var(--fg-2)',
              fontSize: 11, fontWeight: 600, letterSpacing: '.04em',
              cursor: 'pointer',
            }}
          >
            AUTOMATIONS · {AUTOMATIONS.length}
          </button>
          <button
            onClick={() => setTab('runs')}
            style={{
              flex: 1, padding: '11px 12px',
              background: tab === 'runs' ? 'var(--bg-1)' : 'transparent',
              border: 'none', borderBottom: tab === 'runs' ? '2px solid var(--accent)' : '2px solid transparent',
              color: tab === 'runs' ? 'var(--fg-0)' : 'var(--fg-2)',
              fontSize: 11, fontWeight: 600, letterSpacing: '.04em',
              cursor: 'pointer',
            }}
          >
            RUNS · {RUNS.filter(r => r.automation === aut).length}
          </button>
        </div>

        {tab === 'automations' && <AutomationsCol activeId={aut} onSelect={onPickAut} />}
        {tab === 'runs' && (
          <div style={{ display: 'contents' }}>
            <RunsCol automationId={aut} activeRunId={run} onSelect={setRun} />
          </div>
        )}
      </div>

      <RunDetail runId={run} />
    </div>
  );
}

// ─── Variant C: All-runs inbox + slide-over detail ─────────────
// Отдельный экран "All runs" поверх всех automation'ов, как inbox.
// Detail справа, можно закрывать.
function VariantInbox({ defaultRun = 'run_e84a' }) {
  const [run, setRun] = React.useState(defaultRun);
  const [filter, setFilter] = React.useState('all'); // all/running/failed/waiting

  const filtered = RUNS.filter(r =>
    filter === 'all' ? true :
    filter === 'running' ? r.status === 'RUNNING' :
    filter === 'failed' ? r.status === 'FAILED' :
    filter === 'waiting' ? r.status === 'WAITING_HUMAN' : true
  );

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 580px',
      height: 720,
      background: 'var(--bg-0)',
    }}>
      {/* Inbox */}
      <div style={{
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        minHeight: 0,
      }}>
        <div style={{
          padding: '14px 24px 12px',
          borderBottom: '1px solid var(--border)',
          background: 'var(--bg-1)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <I.Inbox style={{ color: 'var(--accent)', width: 16, height: 16 }} />
            <h1 style={{ fontSize: 14, margin: 0, color: 'var(--fg-0)', fontWeight: 600 }}>All runs</h1>
            <span className="dim" style={{ fontSize: 11 }}>across {AUTOMATIONS.length} automations</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: 'var(--fg-2)' }}>
              <b style={{ color: 'var(--running)' }}>{RUNS.filter(r => r.status === 'RUNNING').length} running</b> ·
              {' '}<span style={{ color: 'var(--highlight)' }}>{RUNS.filter(r => r.status === 'WAITING_HUMAN').length} waiting</span> ·
              {' '}<span style={{ color: 'var(--danger)' }}>{RUNS.filter(r => r.status === 'FAILED').length} failed</span>
            </span>
          </div>
          <div className="toolbar" style={{ padding: 0 }}>
            {['all', 'running', 'waiting', 'failed'].map(f => (
              <button key={f}
                className={`filter-pill ${filter === f ? 'active' : ''}`}
                style={{ fontSize: 11 }}
                onClick={() => setFilter(f)}
              >
                {f === 'running' && <span className="dot dot-running" />}
                {f}
                {' '}<span className="dim">{
                  f === 'all' ? RUNS.length :
                  f === 'running' ? RUNS.filter(r => r.status === 'RUNNING').length :
                  f === 'waiting' ? RUNS.filter(r => r.status === 'WAITING_HUMAN').length :
                  RUNS.filter(r => r.status === 'FAILED').length
                }</span>
              </button>
            ))}
            <span style={{ flex: 1 }} />
            <button className="filter-pill" style={{ fontSize: 11 }}>
              <I.Search className="ico-sm" /> поиск
            </button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {filtered.map(r => {
            const automation = AUTOMATIONS.find(a => a.id === r.automation);
            const Icon = I[automation.icon] || I.Bolt;
            return (
              <div key={r.id}
                className={`run-row ${run === r.id ? 'active' : ''}`}
                onClick={() => setRun(r.id)}
                style={{ gridTemplateColumns: '24px 100px 1fr auto', padding: '10px 24px 10px 14px' }}
              >
                <div className={`run-status-dot ${r.status}`} />
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                  <div className="aut-icon" style={{ background: automation.color, width: 18, height: 18, borderRadius: 4 }}>
                    <Icon style={{ width: 10, height: 10 }} />
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {automation.name}
                  </span>
                </div>
                <div style={{ minWidth: 0 }}>
                  <div className="run-meta-line" style={{ marginBottom: 3 }}>
                    <span className="src">{r.trigger.source}</span>
                    <span className="dim">·</span>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--fg-1)' }}>{r.trigger.event_id}</span>
                    <span className="dim">·</span>
                    <span>by {r.trigger.author}</span>
                    {r.session_seq > 1 && (
                      <span style={{ marginLeft: 4, padding: '0 5px', background: 'var(--accent-soft)', color: 'var(--accent)', borderRadius: 3, fontSize: 9.5, fontWeight: 600 }}>
                        #{r.session_seq}
                      </span>
                    )}
                  </div>
                  <div className="run-text" style={{ WebkitLineClamp: 1 }}>{r.trigger.text}</div>
                </div>
                <div className="run-trail">
                  <span>{r.started_at}</span>
                  <span style={{ fontSize: 10 }}>{fmtDur(r.duration_sec)} · ${r.cost_usd.toFixed(2)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <RunDetail runId={run} />
    </div>
  );
}

if (typeof window !== 'undefined') {
  Object.assign(window, { VariantClassic, VariantTwoPane, VariantInbox });
}
