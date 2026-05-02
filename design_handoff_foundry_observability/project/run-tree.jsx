// run-tree.jsx — дерево вызовов агента + sub-agents + milestones rail

// ─── Главный компонент: RunDetail ─────────────────────────────
function RunDetail({ runId }) {
  const run = RUNS.find(r => r.id === runId);
  if (!run) {
    return (
      <div className="col-detail">
        <div className="empty-state" style={{ flex: 1, display: 'grid', placeItems: 'center', color: 'var(--fg-2)' }}>
          <div style={{ textAlign: 'center' }}>
            <I.Sparkle style={{ width: 32, height: 32, color: 'var(--fg-3)', marginBottom: 8 }} />
            <div style={{ fontSize: 13, color: 'var(--fg-1)' }}>Выберите run слева</div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>дерево вызовов агента появится здесь</div>
          </div>
        </div>
      </div>
    );
  }

  const automation = AUTOMATIONS.find(a => a.id === run.automation);
  const tree = RUN_TREES[run.id] || [];
  const Icon = I[TRIG_ICON[run.trigger.kind]] || I.Webhook;

  return (
    <div className="col-detail">
      {/* HEAD: source quote, stats, action buttons */}
      <div className="detail-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span className={`status-pill ${run.status === 'RUNNING' ? 'pill-running' : run.status === 'DONE' ? 'pill-done' : run.status === 'FAILED' ? 'pill-failed' : 'pill-waiting'}`}
            style={{
              padding: '3px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600, letterSpacing: '.04em',
              background: run.status === 'RUNNING' ? 'var(--running-soft)'
                       : run.status === 'DONE' ? 'var(--success-soft)'
                       : run.status === 'FAILED' ? 'var(--danger-soft)'
                       : 'var(--highlight-soft)',
              color: run.status === 'RUNNING' ? 'var(--running)'
                   : run.status === 'DONE' ? 'var(--success)'
                   : run.status === 'FAILED' ? 'var(--danger)'
                   : 'var(--highlight)',
            }}
          >
            {run.status === 'WAITING_HUMAN' ? 'WAITING HUMAN' : run.status}
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-1)' }}>{run.id}</span>
          <span className="dim">·</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-2)' }}>
            session: <span style={{ color: 'var(--accent)' }}>{run.session_id}</span>
            {run.session_seq > 1 && <> · attempt #{run.session_seq}</>}
          </span>
          <span style={{ flex: 1 }} />
          <button className="topbar-btn"><I.Refresh className="ico-sm" /> retry</button>
          <button className="topbar-btn"><I.External className="ico-sm" /> open source</button>
        </div>

        {/* Source quote card */}
        <div className="detail-source-card">
          <div className="detail-source-meta">
            <Icon style={{ width: 12, height: 12 }} />
            <span className="src">{run.trigger.source}</span>
            <span className="dim">·</span>
            <span style={{ fontFamily: 'var(--font-mono)' }}>{run.trigger.event_id}</span>
            <span className="dim">·</span>
            <span>by {run.trigger.author}</span>
          </div>
          <div>{run.trigger.text}</div>
        </div>

        <div className="detail-stats">
          <span><b>{automation?.name}</b> · {automation?.agent.model}</span>
          <span className="sep" style={{ color: 'var(--fg-3)' }}>·</span>
          <span>длительность <b>{fmtDur(run.duration_sec)}</b>{run.status === 'RUNNING' && <span className="live-caret" />}</span>
          <span className="sep" style={{ color: 'var(--fg-3)' }}>·</span>
          <span>стоимость <b>${run.cost_usd.toFixed(2)}</b></span>
          {run.sub_calls > 0 && <>
            <span className="sep" style={{ color: 'var(--fg-3)' }}>·</span>
            <span>{run.sub_calls} sub-agent calls</span>
          </>}
        </div>
      </div>

      {/* SUB-AGENT MINIMAP — только фактически вызванные узлы, кликабельные */}
      <SubagentMinimap tree={tree} />

      {/* TREE */}
      <div className="tree-wrap">
        <TreeNodes nodes={tree} />
      </div>

      {/* CONTINUE COMPOSER — отправить новое сообщение в ту же сессию */}
      <RunComposer run={run} />
    </div>
  );
}

// ─── RunComposer — продолжить беседу / остановить ─────────────
function RunComposer({ run }) {
  const [text, setText] = React.useState('');
  const isRunning = run.status === 'RUNNING';
  const isWaiting = run.status === 'WAITING_HUMAN';

  const placeholder = isRunning
    ? 'Добавить сообщение в очередь, агент увидит его на следующем шаге…'
    : isWaiting
    ? 'Ответьте агенту чтобы продолжить…'
    : `Продолжить session ${run.session_id} — новый attempt #${run.session_seq + 1}`;

  return (
    <div className="run-composer">
      {isRunning && (
        <button className="composer-stop" title="Остановить текущий run">
          <I.Stop style={{ width: 12, height: 12 }} />
          <span>stop</span>
        </button>
      )}
      <div className="composer-field">
        <textarea
          className="composer-input"
          placeholder={placeholder}
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={1}
        />
        <div className="composer-meta">
          <I.Branch style={{ width: 11, height: 11, color: 'var(--fg-3)' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--fg-3)' }}>
            session: <span style={{ color: 'var(--accent)' }}>{run.session_id}</span>
          </span>
          {isRunning && (
            <span style={{ marginLeft: 'auto', fontSize: 10.5, color: 'var(--running)' }}>
              ⏵ агент сейчас работает — сообщение попадёт в очередь
            </span>
          )}
          {isWaiting && (
            <span style={{ marginLeft: 'auto', fontSize: 10.5, color: 'var(--highlight)' }}>
              ⏸ агент ждёт вашего ответа
            </span>
          )}
        </div>
      </div>
      <button
        className={`composer-send ${text.trim() ? 'active' : ''}`}
        disabled={!text.trim()}
        title={isRunning ? 'enqueue' : 'send and continue session'}
      >
        {isRunning ? 'enqueue' : 'continue'}
        <I.Chevron style={{ width: 11, height: 11 }} />
      </button>
    </div>
  );
}

// ─── TreeNodes — рекурсивный рендер ───────────────────────────
function TreeNodes({ nodes, depth = 0 }) {
  return (
    <div className="tree-nodes">
      {nodes.map((n, i) => (
        <TreeNode key={n.id} node={n} first={i === 0} last={i === nodes.length - 1} depth={depth} />
      ))}
    </div>
  );
}

function TreeNode({ node, first, last, depth }) {
  const [open, setOpen] = React.useState(depth === 0 ? false : false);

  if (node.kind === 'subagent') {
    // На верхнем уровне sub-agent читается как раздел: чуть массивнее.
    const isTopLevel = depth === 0;
    return (
      <div className={`tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`} id={`sa-${node.id}`}>
        <div className="tree-rail">
          <span className="tree-glyph subagent"><I.Branch /></span>
        </div>
        <div className="tree-body">
          <div className={`subagent-block ${isTopLevel ? 'top' : ''}`}>
            <div className={`subagent-head ${open ? 'open' : ''}`} onClick={() => setOpen(o => !o)}>
              <I.ChevronRight className={`subagent-chev ${open ? 'open' : ''}`} style={{ width: 12, height: 12 }} />
              <div style={{ minWidth: 0 }}>
                <div className="subagent-title">
                  <span className="subagent-kind-tag">sub-agent</span>
                  <span className="subagent-name">{node.agent}</span>
                </div>
                <div className="subagent-summary">{node.summary}</div>
              </div>
              <span className="subagent-stats">{fmtDur(node.duration_sec)} · ${node.cost_usd.toFixed(2)}</span>
              <I.External style={{ width: 11, height: 11, color: 'var(--fg-3)' }} />
            </div>
            {open && (
              <div className="subagent-children">
                <TreeNodes nodes={node.children} depth={depth + 1} />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (node.kind === 'milestone') {
    // Legacy — остаётся для обратной совместимости, но теперь рендерим как тонкий divider
    return null;
  }

  if (node.kind === 'skill') {
    return (
      <div className={`tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}>
        <div className="tree-rail">
          <span className="tree-glyph skill"><I.Bolt /></span>
        </div>
        <div className="tree-body">
          <div className="tree-skill-line">
            <span style={{ fontSize: 9.5, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '.08em', fontWeight: 700 }}>skill</span>
            <span className="tree-skill-name">{node.skill}</span>
            {node.detail && <span className="tree-skill-detail">{node.detail}</span>}
            <span style={{ flex: 1 }} />
            {node.ts && <span style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>{node.ts}</span>}
          </div>
        </div>
      </div>
    );
  }

  if (node.kind === 'tool') {
    return (
      <div className={`tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}>
        <div className="tree-rail">
          <span className="tree-glyph tool">⚙</span>
        </div>
        <div className="tree-body">
          <div className="tree-tool-line">
            <span className="tree-tool-name">{node.tool}</span>
            <span className="tree-tool-detail">{node.detail}</span>
            {node.files && <span style={{ color: 'var(--fg-3)', fontSize: 10.5 }}>· {node.files} files</span>}
            {node.live && <span className="live-caret" />}
          </div>
        </div>
      </div>
    );
  }

  if (node.kind === 'thinking') {
    return (
      <div className={`tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}>
        <div className="tree-rail">
          <span className="tree-glyph thinking">◇</span>
        </div>
        <div className="tree-body">
          <div className="tree-thinking">{node.text}{node.live && <span className="live-caret" />}</div>
        </div>
      </div>
    );
  }

  if (node.kind === 'final') {
    return (
      <div className={`tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}>
        <div className="tree-rail">
          <span className="tree-glyph final"><I.Check /></span>
        </div>
        <div className="tree-body">
          <div style={{ fontSize: 12, color: 'var(--fg-1)', padding: '4px 10px', background: 'var(--success-soft)', borderRadius: 'var(--r-sm)', display: 'inline-block' }}>
            {node.text}
          </div>
        </div>
      </div>
    );
  }

  // text (default)
  return (
    <div className={`tree-node ${first ? 'first' : ''} ${last ? 'last' : ''}`}>
      <div className="tree-rail">
        <span className="tree-glyph">▸</span>
      </div>
      <div className="tree-body">
        <div className="tree-text">{node.text}{node.live && <span className="live-caret" />}</div>
      </div>
    </div>
  );
}

// ─── SubagentMinimap — узкая лента вызванных sub-agents ────────
function SubagentMinimap({ tree }) {
  // Собираем только top-level sub-agent узлы (фактически вызванные)
  const subs = tree.filter(n => n.kind === 'subagent');
  if (subs.length === 0) return null;

  const scrollTo = (id) => {
    const el = document.getElementById(`sa-${id}`);
    if (el) {
      const wrap = el.closest('.tree-wrap');
      if (wrap) {
        const top = el.offsetTop - wrap.offsetTop - 40;
        wrap.scrollTo({ top, behavior: 'smooth' });
      }
    }
  };

  return (
    <div className="subagent-minimap">
      <span className="minimap-label">sub-agents called:</span>
      <div className="minimap-track">
        {subs.map((s, i) => (
          <React.Fragment key={s.id}>
            {i > 0 && <span className="minimap-sep">›</span>}
            <button className="minimap-pill" onClick={() => scrollTo(s.id)}>
              <I.Branch style={{ width: 10, height: 10 }} />
              <span>{s.agent}</span>
              <span className="minimap-meta">{fmtDur(s.duration_sec)}</span>
            </button>
          </React.Fragment>
        ))}
      </div>
      <span style={{ flex: 1 }} />
      <span className="minimap-hint">по факту вызовов · top-level агент решает сам</span>
    </div>
  );
}

if (typeof window !== 'undefined') {
  Object.assign(window, { SubagentMinimap });
}
