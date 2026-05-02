// automations-shell.jsx — три колонки + run details со всем содержимым

// ─── Helpers ──────────────────────────────────────────────────
const TRIG_ICON = { github: 'GitHub', discord: 'Discord', cron: 'Clock', webhook: 'Webhook' };

function fmtDur(s) {
  if (s < 60) return `${s}с`;
  const m = Math.floor(s / 60), r = s % 60;
  return r ? `${m}м ${r}с` : `${m}м`;
}

// ─── Колонка 1 — Automations ──────────────────────────────────
function AutomationsCol({ activeId, onSelect }) {
  return (
    <div className="col-automations">
      <div className="col-automations-head">
        <I.Bolt style={{ color: 'var(--accent)' }} />
        <h2>Automations</h2>
        <span style={{ flex: 1 }} />
        <button className="topbar-btn"><I.Plus className="ico-sm" />New</button>
      </div>

      <div className="col-automations-list">
        {AUTOMATIONS.map(a => {
          const Icon = I[a.icon] || I.Bolt;
          return (
            <div
              key={a.id}
              className={`aut-row ${activeId === a.id ? 'active' : ''} ${a.counts.running ? 'has-running' : 'idle'}`}
              onClick={() => onSelect(a.id)}
            >
              <div className="aut-icon" style={{ background: a.color }}>
                <Icon />
              </div>
              <div style={{ minWidth: 0 }}>
                <div className="aut-name">{a.name}</div>
                <div className="aut-desc">{a.description}</div>
              </div>
              {a.counts.running > 0 && (
                <span className="aut-running-badge">
                  {a.counts.running} <span style={{ fontSize: 9, opacity: .7 }}>RUN</span>
                </span>
              )}
            </div>
          );
        })}
      </div>

      <div className="col-triggers">
        <div className="col-triggers-head">
          <I.Webhook style={{ width: 11, height: 11 }} />
          <span>Triggers</span>
          <span style={{ flex: 1 }} />
          <span className="dim" style={{ fontVariantNumeric: 'tabular-nums', fontSize: 10 }}>
            {TRIGGERS.filter(t => t.health === 'ok').length}/{TRIGGERS.length} ok
          </span>
        </div>
        {TRIGGERS.map(t => {
          const Icon = I[TRIG_ICON[t.kind]] || I.Webhook;
          return (
            <div key={t.id} className="trig-row" title={t.detail}>
              <div className="trig-icon"><Icon /></div>
              <div className={`health-dot ${t.health}`} />
              <span className="trig-name">{t.name}</span>
              <span className="trig-seen">{t.last_seen}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Колонка 2 — Runs ─────────────────────────────────────────
function RunsCol({ automationId, activeRunId, onSelect, theme }) {
  const automation = AUTOMATIONS.find(a => a.id === automationId);
  const runs = RUNS.filter(r => r.automation === automationId);
  const Icon = I[automation?.icon] || I.Bolt;

  // Группировка по session_id для рисования вертикальной нити
  const sessionGroups = React.useMemo(() => {
    const groups = {};
    runs.forEach((r, i) => {
      if (!groups[r.session_id]) groups[r.session_id] = [];
      groups[r.session_id].push({ ...r, _idx: i });
    });
    return Object.values(groups).filter(g => g.length > 1);
  }, [runs]);

  return (
    <div className="col-runs">
      <div className="col-runs-head">
        <div className="aut-icon" style={{ background: automation?.color }}>
          <Icon />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--fg-0)', fontFamily: 'var(--font-mono)' }}>
            {automation?.name}
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--fg-2)' }}>
            <b style={{ color: 'var(--running)' }}>{automation?.counts.running} running</b> ·
            {' '}{automation?.counts.today} today ·
            {' '}{automation?.counts.week} this week
            {automation?.counts.failed_today > 0 && <> · <span style={{ color: 'var(--danger)' }}>{automation?.counts.failed_today} failed</span></>}
          </div>
        </div>
      </div>

      {/* Filter pills */}
      <div className="toolbar" style={{ padding: '8px 14px', borderBottom: '1px solid var(--border-soft)' }}>
        <button className="filter-pill active" style={{ fontSize: 10.5 }}>Все <span className="dim">{runs.length}</span></button>
        <button className="filter-pill" style={{ fontSize: 10.5 }}><span className="dot dot-running" />running</button>
        <button className="filter-pill" style={{ fontSize: 10.5 }}>failed</button>
        <button className="filter-pill" style={{ fontSize: 10.5 }}>waiting</button>
      </div>

      <div className="col-runs-list">
        {/* Session lines (drawn beneath rows) */}
        {sessionGroups.map(g => {
          const ROW_H = 36;                            // approx after pill-row pass
          const top = g[0]._idx * ROW_H + 18;
          const bottom = g[g.length - 1]._idx * ROW_H + 18;
          return <div key={g[0].session_id} className="session-line" style={{ top, height: bottom - top }} />;
        })}

        {runs.map(r => {
          const inSession = sessionGroups.some(g => g.some(x => x.id === r.id));
          return (
            <div
              key={r.id}
              className={`run-row ${activeRunId === r.id ? 'active' : ''} ${inSession ? 'in-session' : ''}`}
              onClick={() => onSelect(r.id)}
            >
              <div className={`run-status-dot ${r.status}`} />
              <div style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="run-source">
                  {r.trigger.event_id}
                </span>
                {r.session_seq > 1 && (
                  <span className="seq-pill">#{r.session_seq}</span>
                )}
                <span className="run-text-inline">{r.trigger.text}</span>
              </div>
              <div className="run-trail">
                {r.status === 'WAITING_HUMAN' && <span className="trail-tag waiting">human</span>}
                {r.status === 'FAILED' && <span className="trail-tag failed">failed</span>}
                {r.status === 'RUNNING' && <span className="trail-tag running">{fmtDur(r.duration_sec)}</span>}
                {r.status === 'DONE' && <span className="trail-meta">{fmtDur(r.duration_sec)} · ${r.cost_usd.toFixed(2)}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Колонка 3 — Run Details (см. run-tree.jsx) ───────────────
// рендерится из main.

if (typeof window !== 'undefined') {
  Object.assign(window, { AutomationsCol, RunsCol, fmtDur });
}
