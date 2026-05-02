// automations-v2.jsx — Variant B + claude.app visual language
// Левая панель (360px) с табами Automations / Runs / Inbox + Triggers внизу.
// Правая колонка — Run Detail с дерева вызовов и composer'ом.

// ─── helpers ──────────────────────────────────────────────────
const TRIG_ICON_V2 = { github: 'GitHub', discord: 'Discord', cron: 'Clock', webhook: 'Webhook' };

function fmtDurV2(s) {
  if (s < 60) return `${s}с`;
  const m = Math.floor(s / 60), r = s % 60;
  return r ? `${m}м ${r}с` : `${m}м`;
}

const STATUS_GLYPH = {
  RUNNING: 'running',
  DONE: 'done',
  FAILED: 'failed',
  WAITING_HUMAN: 'waiting',
  SKIPPED: 'skipped',
};
const STATUS_WORD = {
  RUNNING: 'Running',
  DONE: 'Done',
  FAILED: 'Failed',
  WAITING_HUMAN: 'Waiting',
  SKIPPED: 'Skipped',
};

const FAILURE_LABELS = {
  deterministic: { word: 'Тесты/lint',    tooltip: 'объективно сломано: тесты, lint, типы, build' },
  acceptance:    { word: 'Не по задаче',  tooltip: 'работает, но не делает то, что просили' },
  infra:         { word: 'Инфра',         tooltip: 'сетевой/CI флак — можно retry' },
  unclear:       { word: 'Непонятно',     tooltip: 'verifier не разобрался, нужен человек' },
  dangerous:     { word: 'Опасно',        tooltip: 'действие требует ручного апрува' },
};

// Single, mono status glyph
function StatusGlyph({ status, size }) {
  const cls = STATUS_GLYPH[status] || 'pending';
  const style = size ? { width: size, height: size } : null;
  return (
    <span className={`v2-glyph ${cls}`} style={style}>
      {cls === 'done' && <I.Check />}
    </span>
  );
}

// ─── Top-level App ────────────────────────────────────────────
function AutomationsV2({ defaultTab = 'automations', defaultAut = 'dev_task', defaultRun = 'run_e84a', inboxFilter }) {
  const [tab, setTab]   = React.useState(defaultTab);     // 'automations' | 'runs' | 'inbox'
  const [aut, setAut]   = React.useState(defaultAut);
  const [run, setRun]   = React.useState(defaultRun);
  const [filter, setFilter] = React.useState(inboxFilter || 'all');

  const onPickAut = (id) => {
    setAut(id);
    setTab('runs');
    const first = RUNS.find(r => r.automation === id);
    if (first) setRun(first.id);
  };

  const runsForAut = RUNS.filter(r => r.automation === aut);
  const filteredInbox = RUNS.filter(r =>
    filter === 'all' ? true :
    filter === 'running' ? r.status === 'RUNNING' :
    filter === 'failed'  ? r.status === 'FAILED' :
    filter === 'waiting' ? r.status === 'WAITING_HUMAN' : true
  );

  const totalCounts = {
    running: RUNS.filter(r => r.status === 'RUNNING').length,
    waiting: RUNS.filter(r => r.status === 'WAITING_HUMAN').length,
    failed:  RUNS.filter(r => r.status === 'FAILED').length,
  };

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '360px 1fr',
      height: '100%',
      background: 'var(--bg-0)',
    }}>
      <SidebarV2
        tab={tab} setTab={setTab}
        aut={aut} run={run} setRun={setRun}
        onPickAut={onPickAut}
        filter={filter} setFilter={setFilter}
        runsForAut={runsForAut}
        filteredInbox={filteredInbox}
        totalCounts={totalCounts}
      />
      <RunDetailV2 runId={run} onPickAut={onPickAut} />
    </div>
  );
}

// ─── Sidebar (3 tabs + triggers footer in automations tab) ───
function SidebarV2({ tab, setTab, aut, run, setRun, onPickAut, filter, setFilter, runsForAut, filteredInbox, totalCounts }) {
  return (
    <div className="v2-sidebar">
      <div className="v2-sidebar-tabs">
        <button className={`v2-tab ${tab === 'automations' ? 'active' : ''}`} onClick={() => setTab('automations')}>
          <I.Bolt /> automations
          <span className="v2-tab-count">{AUTOMATIONS.length}</span>
        </button>
        <button className={`v2-tab ${tab === 'runs' ? 'active' : ''}`} onClick={() => setTab('runs')}>
          <I.Branch /> runs
          <span className="v2-tab-count">{runsForAut.length}</span>
        </button>
        <button className={`v2-tab ${tab === 'inbox' ? 'active' : ''}`} onClick={() => setTab('inbox')}>
          <I.Inbox /> inbox
          <span className="v2-tab-count">{RUNS.length}</span>
        </button>
      </div>

      <div className="v2-pane-body">
        {tab === 'automations' && <AutomationsListV2 activeId={aut} onSelect={onPickAut} />}
        {tab === 'runs' && (
          <RunsListV2 aut={aut} runs={runsForAut} activeRunId={run} onSelect={setRun} onBack={() => setTab('automations')} />
        )}
        {tab === 'inbox' && (
          <InboxListV2 runs={filteredInbox} activeRunId={run} onSelect={setRun} filter={filter} setFilter={setFilter} totalCounts={totalCounts} />
        )}
      </div>
    </div>
  );
}

// ─── Automations list (claude.app routines style) ────────────
function AutomationsListV2({ activeId, onSelect }) {
  return (
    <div>
      <div className="v2-aut-list">
        {AUTOMATIONS.map(a => {
          const Icon = I[a.icon] || I.Bolt;
          const active = a.counts.running > 0 || a.counts.today > 0;
          return (
            <div
              key={a.id}
              className={`v2-aut-row ${activeId === a.id ? 'active' : ''}`}
              onClick={() => onSelect(a.id)}
            >
              <span className="v2-aut-icon"><Icon /></span>
              <div style={{ minWidth: 0 }}>
                <div className="v2-aut-name">{a.name}</div>
                <div className="v2-aut-desc">{a.description}</div>
              </div>
              <div className={`v2-aut-state ${active ? 'active' : ''}`}>
                {a.counts.running > 0 ? `${a.counts.running} running` : 'Active'}
                <span className="v2-toggle"></span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="v2-triggers">
        <div className="v2-triggers-head">
          <I.Webhook style={{ width: 10, height: 10 }} /> Triggers
          <span style={{ flex: 1 }}></span>
          <span style={{ color: 'var(--fg-3)', fontSize: 10 }}>
            {TRIGGERS.filter(t => t.health === 'ok').length}/{TRIGGERS.length} ok
          </span>
        </div>
        {TRIGGERS.map(t => (
          <div key={t.id} className="v2-trig-row" title={t.detail}>
            <span className={`v2-trig-dot ${t.health}`}></span>
            <span className="v2-trig-name">{t.name}</span>
            <span className="v2-trig-seen">{t.last_seen}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Runs list (one automation) ───────────────────────────────
function RunsListV2({ aut, runs, activeRunId, onSelect, onBack }) {
  const automation = AUTOMATIONS.find(a => a.id === aut);
  const Icon = I[automation?.icon] || I.Bolt;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="v2-runs-head">
        <div className="v2-runs-head-top">
          <button className="v2-runs-back" onClick={onBack}>
            <I.ChevronLeft style={{ width: 11, height: 11 }} /> automations
          </button>
        </div>
        <div className="v2-runs-head-top">
          <Icon style={{ width: 14, height: 14, color: 'var(--fg-2)' }} />
          <span className="v2-runs-title" style={{ fontFamily: 'var(--font-mono)' }}>{automation?.name}</span>
        </div>
        <div className="v2-runs-counts">
          {automation?.counts.running > 0 && <><b style={{ color: 'var(--running)' }}>{automation.counts.running} running</b> · </>}
          <b>{automation?.counts.today}</b> today · <b>{automation?.counts.week}</b> this week
          {automation?.counts.failed_today > 0 && <> · <b style={{ color: 'var(--danger)' }}>{automation.counts.failed_today} failed</b></>}
        </div>
      </div>

      <div className="v2-runs-list">
        {runs.map(r => (
          <RunRowV2 key={r.id} run={r} active={activeRunId === r.id} onClick={() => onSelect(r.id)} />
        ))}
      </div>
    </div>
  );
}

// ─── Inbox list ───────────────────────────────────────────────
function InboxListV2({ runs, activeRunId, onSelect, filter, setFilter, totalCounts }) {
  const counts = {
    all: RUNS.length,
    running: totalCounts.running,
    waiting: totalCounts.waiting,
    failed: totalCounts.failed,
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="v2-runs-head">
        <div className="v2-runs-head-top">
          <I.Inbox style={{ width: 14, height: 14, color: 'var(--fg-2)' }} />
          <span className="v2-runs-title">All runs</span>
        </div>
        <div className="v2-runs-counts">
          across {AUTOMATIONS.length} automations
          {totalCounts.running > 0 && <> · <b style={{ color: 'var(--running)' }}>{totalCounts.running} running</b></>}
          {totalCounts.waiting > 0 && <> · <b style={{ color: 'var(--highlight)' }}>{totalCounts.waiting} waiting</b></>}
          {totalCounts.failed > 0 && <> · <b style={{ color: 'var(--danger)' }}>{totalCounts.failed} failed</b></>}
        </div>
      </div>
      <div className="v2-filter-bar">
        {['all','running','waiting','failed'].map(f => (
          <button key={f} className={`v2-filter ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
            {f === 'running' && <span className="v2-glyph running" style={{ width: 8, height: 8 }}></span>}
            {f}
            <span className="v2-filter-count">{counts[f]}</span>
          </button>
        ))}
      </div>
      <div className="v2-runs-list">
        {runs.map(r => (
          <RunRowV2 key={r.id} run={r} active={activeRunId === r.id} onClick={() => onSelect(r.id)} inbox />
        ))}
      </div>
    </div>
  );
}

// ─── Run row ──────────────────────────────────────────────────
function RunRowV2({ run, active, onClick, inbox }) {
  const automation = AUTOMATIONS.find(a => a.id === run.automation);
  const AIcon = automation && (I[automation.icon] || I.Bolt);
  return (
    <div className={`v2-run-row ${active ? 'active' : ''} ${inbox ? 'v2-inbox-row' : ''}`} onClick={onClick}>
      <StatusGlyph status={run.status} />
      {inbox && (
        <span className="v2-inbox-aut">
          <AIcon /> <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{automation.name}</span>
        </span>
      )}
      <div className="v2-run-meta">
        <div className="v2-run-title">
          <span className="v2-run-event">{run.trigger.event_id}</span>
          {run.session_seq > 1 && <span className="v2-attempt-badge">attempt {run.session_seq}</span>}
          <span className="v2-run-text">{run.trigger.text}</span>
        </div>
        <div className="v2-run-sub">
          <span className="src">{run.trigger.source}</span>
          <span className="dot">·</span>
          <span className="author">by {run.trigger.author}</span>
        </div>
      </div>
      <div className="v2-run-trail">
        <span className={`status-word ${STATUS_GLYPH[run.status]}`}>
          {run.status === 'RUNNING' ? fmtDurV2(run.duration_sec) : STATUS_WORD[run.status]}
        </span>
        {run.status !== 'RUNNING' && <span>{fmtDurV2(run.duration_sec)} · ${run.cost_usd.toFixed(2)}</span>}
      </div>
    </div>
  );
}

// ─── Run Detail ───────────────────────────────────────────────
function RunDetailV2({ runId, onPickAut }) {
  const run = RUNS.find(r => r.id === runId);
  if (!run) {
    return (
      <div className="v2-detail">
        <div className="v2-empty">
          <div className="v2-empty-inner">
            <I.Sparkle className="icon" />
            <div className="title">Выберите run слева</div>
            <div className="sub">Дерево вызовов агента появится здесь</div>
          </div>
        </div>
      </div>
    );
  }

  const automation = AUTOMATIONS.find(a => a.id === run.automation);
  const tree = RUN_TREES[run.id] || [];
  const TIcon = I[TRIG_ICON_V2[run.trigger.kind]] || I.Webhook;
  const AIcon = automation && (I[automation.icon] || I.Bolt);
  const status = run.status;
  const failure = run.failure_kind && FAILURE_LABELS[run.failure_kind];

  return (
    <div className="v2-detail">
      <div className="v2-detail-head">
        <div className="v2-detail-headrow">
          <span className={`v2-status-pill ${STATUS_GLYPH[status]}`}>
            <StatusGlyph status={status} />
            {STATUS_WORD[status]}
          </span>
          <button className="v2-aut-pill" onClick={() => onPickAut && onPickAut(automation.id)}>
            <AIcon />{automation.name}
          </button>
          <span className="v2-session-info">
            <span className="session-id">{run.session_id}</span>
            {run.session_seq > 1 && <span className="attempt"> · attempt {run.session_seq}</span>}
          </span>
          {failure && (
            <span className={`v2-failure-pill ${run.failure_kind}`} title={failure.tooltip}>
              {failure.word}
            </span>
          )}
          <span style={{ flex: 1 }}></span>
          <button className="topbar-btn"><I.Refresh className="ico-sm" /> retry</button>
          <button className="topbar-btn"><I.External className="ico-sm" /> open source</button>
        </div>

        <div className="v2-source-card">
          <div className="v2-source-meta">
            <TIcon />
            <span className="src">{run.trigger.source}</span>
            <span className="dot">·</span>
            <span style={{ fontFamily: 'var(--font-mono)' }}>{run.trigger.event_id}</span>
            <span className="dot">·</span>
            <span>by {run.trigger.author}</span>
          </div>
          <div>{run.trigger.text}</div>
        </div>

        <div className="v2-detail-stats">
          <span><b>{automation?.agent.model}</b></span>
          <span className="sep">·</span>
          <span>длительность <b>{fmtDurV2(run.duration_sec)}</b>{status === 'RUNNING' && <span className="live-caret"></span>}</span>
          <span className="sep">·</span>
          <span>стоимость <b>${run.cost_usd.toFixed(2)}</b></span>
          {run.sub_calls > 0 && <>
            <span className="sep">·</span>
            <span><b>{run.sub_calls}</b> sub-agent calls</span>
          </>}
          {run.failure_msg && <>
            <span className="sep">·</span>
            <span style={{ color: 'var(--danger)' }}>{run.failure_msg}</span>
          </>}
          {run.waiting_reason && <>
            <span className="sep">·</span>
            <span style={{ color: 'var(--highlight)' }}>{run.waiting_reason}</span>
          </>}
        </div>
      </div>

      <SubagentMinimapV2 tree={tree} />

      <div className="v2-tree-wrap">
        <TreeNodesV2 nodes={tree} />
      </div>

      <RunComposerV2 run={run} />
    </div>
  );
}

// ─── Tree ─────────────────────────────────────────────────────
function TreeNodesV2({ nodes, depth = 0 }) {
  return (
    <div>
      {nodes.map((n, i) => (
        <TreeNodeV2 key={n.id} node={n} first={i === 0} last={i === nodes.length - 1} depth={depth} />
      ))}
    </div>
  );
}

function TreeNodeV2({ node, first, last, depth }) {
  const [open, setOpen] = React.useState(false);

  // mark_milestone — bright divider, не tree-row
  if (node.kind === 'mark') {
    return (
      <div className="v2-mark">
        <span className="v2-mark-bullet"></span>
        <span className="v2-mark-label">{node.label}</span>
        <span className="v2-mark-line"></span>
      </div>
    );
  }

  if (node.kind === 'subagent') {
    const isTop = depth === 0;
    return (
      <div className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`} id={`sa-${node.id}`}>
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph subagent"><I.Branch /></span>
        </div>
        <div className="v2-tree-body">
          <div className={`v2-sub ${isTop ? 'top' : ''}`}>
            <div className={`v2-sub-head ${open ? 'open' : ''}`} onClick={() => setOpen(o => !o)}>
              <span className={`v2-sub-chev ${open ? 'open' : ''}`}>▸</span>
              <div style={{ minWidth: 0 }}>
                <div className="v2-sub-title">
                  <span className="v2-sub-tag">sub-agent</span>
                  <span className="v2-sub-name">{node.agent}</span>
                </div>
                <div className="v2-sub-summary">{node.summary}</div>
              </div>
              <span className="v2-sub-stats">{fmtDurV2(node.duration_sec)} · ${node.cost_usd.toFixed(2)}</span>
            </div>
            {open && (
              <div className="v2-sub-children">
                <TreeNodesV2 nodes={node.children} depth={depth + 1} />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (node.kind === 'skill') {
    return (
      <div className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}>
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph skill"><I.Bolt /></span>
        </div>
        <div className="v2-tree-body">
          <div className="v2-tree-skill">
            <span className="label">skill</span>
            <span className="name">{node.skill}</span>
            {node.detail && <span className="detail">{node.detail}</span>}
            <span style={{ flex: 1 }}></span>
            {node.ts && <span style={{ fontSize: 10, color: 'var(--fg-3)' }}>{node.ts}</span>}
          </div>
        </div>
      </div>
    );
  }

  if (node.kind === 'tool') {
    return (
      <div className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}>
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph tool">⚙</span>
        </div>
        <div className="v2-tree-body">
          <div className="v2-tree-tool">
            <span className="v2-tree-tool-name">{node.tool}</span>
            <span className="v2-tree-tool-detail">{node.detail}</span>
            {node.files && <span className="v2-tree-tool-meta">· {node.files} files</span>}
            {node.live && <span className="live-caret"></span>}
          </div>
        </div>
      </div>
    );
  }

  if (node.kind === 'thinking') {
    return (
      <div className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}>
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph thinking">◇</span>
        </div>
        <div className="v2-tree-body">
          <div className="v2-tree-thinking">{node.text}{node.live && <span className="live-caret"></span>}</div>
        </div>
      </div>
    );
  }

  if (node.kind === 'final') {
    return (
      <div className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}>
        <div className="v2-tree-rail">
          <span className="v2-tree-glyph final"><I.Check /></span>
        </div>
        <div className="v2-tree-body">
          <div style={{ fontSize: 12, color: 'var(--fg-1)' }}>{node.text}</div>
        </div>
      </div>
    );
  }

  // text
  return (
    <div className={`v2-tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}>
      <div className="v2-tree-rail">
        <span className="v2-tree-glyph">▸</span>
      </div>
      <div className="v2-tree-body">
        <div className="v2-tree-text">{node.text}{node.live && <span className="live-caret"></span>}</div>
      </div>
    </div>
  );
}

// ─── Sub-agent minimap (v2) ───────────────────────────────────
function SubagentMinimapV2({ tree }) {
  const subs = tree.filter(n => n.kind === 'subagent');
  if (subs.length === 0) return null;
  const scrollTo = (id) => {
    const el = document.getElementById(`sa-${id}`);
    if (el) {
      const wrap = el.closest('.v2-tree-wrap');
      if (wrap) {
        const top = el.offsetTop - wrap.offsetTop - 30;
        wrap.scrollTo({ top, behavior: 'smooth' });
      }
    }
  };
  return (
    <div className="v2-minimap">
      <span className="v2-minimap-label">sub-agents called</span>
      <div className="v2-minimap-track">
        {subs.map((s, i) => (
          <React.Fragment key={s.id}>
            {i > 0 && <span className="v2-minimap-sep">›</span>}
            <button className="v2-minimap-pill" onClick={() => scrollTo(s.id)}>
              <I.Branch /><span>{s.agent}</span>
              <span className="v2-minimap-meta">{fmtDurV2(s.duration_sec)}</span>
            </button>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

// ─── Composer (claude.app code session input) ────────────────
function RunComposerV2({ run }) {
  const [text, setText] = React.useState('');
  const isRunning = run.status === 'RUNNING';
  const isWaiting = run.status === 'WAITING_HUMAN';

  const placeholder = isRunning
    ? 'Добавить сообщение в очередь, агент увидит его на следующем шаге…'
    : isWaiting
    ? 'Ответьте чтобы продолжить…'
    : `Продолжить session — новый attempt #${run.session_seq + 1}`;

  return (
    <div className="v2-composer">
      <div className="v2-composer-field">
        <textarea
          className="v2-composer-input"
          placeholder={placeholder}
          value={text}
          onChange={e => setText(e.target.value)}
          rows={1}
        />
        <div className="v2-composer-actions">
          <span className="v2-composer-hint">
            session: <span style={{ color: 'var(--accent)' }}>{run.session_id}</span>
            {isRunning && <span style={{ color: 'var(--running)', marginLeft: 8 }}>⏵ агент работает — попадёт в очередь</span>}
            {isWaiting && <span style={{ color: 'var(--highlight)', marginLeft: 8 }}>⏸ агент ждёт ответа</span>}
          </span>
          {isRunning && (
            <button className="v2-composer-stop"><I.Stop style={{ width: 10, height: 10 }} /> stop</button>
          )}
          <button className={`v2-composer-send ${text.trim() ? 'active' : ''}`} disabled={!text.trim()}>
            {isRunning ? 'enqueue' : isWaiting ? 'reply' : 'continue'}
            <I.Chevron style={{ width: 10, height: 10 }} />
          </button>
        </div>
      </div>
    </div>
  );
}

if (typeof window !== 'undefined') {
  Object.assign(window, {
    AutomationsV2, SidebarV2, AutomationsListV2,
    RunsListV2, InboxListV2, RunRowV2,
    RunDetailV2, TreeNodesV2, TreeNodeV2,
    SubagentMinimapV2, RunComposerV2,
    StatusGlyph, fmtDurV2,
  });
}
