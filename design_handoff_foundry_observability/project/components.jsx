// components.jsx — переиспользуемые блоки UI для Foundry Observability
// StageStepper, EventRow (в 3-х стилях), StatusChip, TaskRow, TaskDetails

// ─── Status chip ────────────────────────────────────────────
function StatusChip({ status }) {
  if (status === 'RUNNING') return (
    <span className="chip chip-running"><span className="dot dot-running" />RUNNING</span>
  );
  if (status === 'DONE')    return <span className="chip chip-done"><I.Check className="ico-sm"/>DONE</span>;
  if (status === 'FAILED')  return <span className="chip chip-failed"><I.X className="ico-sm"/>FAILED</span>;
  if (status === 'PENDING') return <span className="chip chip-pending"><span className="dot dot-pending"/>PENDING</span>;
  return <span className="chip chip-pending">{status}</span>;
}

// ─── Stage stepper ──────────────────────────────────────────
// Горизонтальные точки с соединителями. Поддерживает 3 размера.
// При size=lg и передаче onStageClick — становится интерактивным:
// кликабельные стадии, выбранная подсвечивается.
function StageStepper({ stages, size = 'md', showLabels = true, onStageClick, selectedStage }) {
  const sizes = {
    sm: { dot: 6,  gap: 28, labelFs: 10, connH: 1 },
    md: { dot: 8,  gap: 36, labelFs: 10.5, connH: 1 },
    lg: { dot: 10, gap: 50, labelFs: 11, connH: 1.5 },
  }[size];
  const interactive = !!onStageClick;

  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      {STAGES.map((s, idx) => {
        const st = stages[s.id] || { status: 'pending' };
        const next = idx < STAGES.length - 1 ? (stages[STAGES[idx+1].id] || { status: 'pending' }) : null;
        const isDone = st.status === 'done';
        const isRunning = st.status === 'running';
        const isFailed = st.status === 'failed';
        const isSkipped = st.status === 'skipped';
        const isPending = st.status === 'pending' || !st.status;
        const isSelected = interactive && selectedStage === s.id;
        const clickable = interactive && !isPending;

        let dotColor = 'var(--fg-3)';
        let ring = null;
        let content = null;
        if (isDone)    { dotColor = 'var(--success)'; content = <I.Check style={{ width: 7, height: 7, color: '#fff', strokeWidth: 3 }} />; }
        if (isRunning) { dotColor = 'var(--running)'; ring = true; }
        if (isFailed)  { dotColor = 'var(--danger)';  content = <I.X style={{ width: 7, height: 7, color: '#fff', strokeWidth: 3 }} />; }
        if (isSkipped) { dotColor = 'var(--bg-3)'; }

        // цвет соединителя
        let connColor = 'var(--border)';
        if (isDone && next && (next.status === 'done' || next.status === 'running' || next.status === 'failed')) {
          connColor = 'var(--success)';
        }

        const dotSize = sizes.dot + 6;

        return (
          <React.Fragment key={s.id}>
            <div
              onClick={clickable ? () => onStageClick(s.id) : undefined}
              style={{
                position: 'relative',
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                cursor: clickable ? 'pointer' : 'default',
                padding: interactive ? '4px 8px 22px' : 0,
                borderRadius: 8,
                background: isSelected ? 'var(--bg-2)' : 'transparent',
                transition: 'background .15s',
              }}
              onMouseEnter={(e) => { if (clickable && !isSelected) e.currentTarget.style.background = 'var(--bg-1)'; }}
              onMouseLeave={(e) => { if (clickable && !isSelected) e.currentTarget.style.background = 'transparent'; }}
            >
              <div style={{
                width: dotSize, height: dotSize,
                borderRadius: '50%',
                background: dotColor,
                display: 'grid', placeItems: 'center',
                boxShadow: ring
                  ? '0 0 0 3px var(--running-soft)'
                  : isSelected ? `0 0 0 2px var(--accent)` : 'none',
                animation: ring ? 'pulse-dot 1.4s ease-in-out infinite' : 'none',
                border: isSkipped ? '1px dashed var(--border-strong)' : 'none',
                flexShrink: 0,
                transition: 'box-shadow .15s',
              }}>
                {content}
              </div>
              {showLabels && (
                <span style={{
                  position: 'absolute', top: (interactive ? 4 : 0) + dotSize + 6,
                  fontSize: sizes.labelFs,
                  color: isSelected ? 'var(--accent)'
                    : isRunning ? 'var(--running)'
                    : isDone ? 'var(--fg-1)'
                    : isFailed ? 'var(--danger)'
                    : 'var(--fg-3)',
                  fontWeight: isRunning || isFailed || isSelected ? 600 : 400,
                  letterSpacing: '.01em',
                  whiteSpace: 'nowrap',
                }}>{s.label}</span>
              )}
            </div>
            {idx < STAGES.length - 1 && (
              <div style={{
                width: sizes.gap, height: sizes.connH,
                background: connColor,
                flexShrink: 0,
                transition: 'background .3s',
                marginBottom: interactive ? 18 : 0,
              }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ─── Compact stepper (только точки, без подписей, для карточки в списке) ─
function StageDots({ stages }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
      {STAGES.map((s, idx) => {
        const st = stages[s.id] || { status: 'pending' };
        let bg = 'var(--bg-3)';
        let anim = null;
        if (st.status === 'done') bg = 'var(--success)';
        if (st.status === 'running') { bg = 'var(--running)'; anim = 'pulse-dot 1.4s ease-in-out infinite'; }
        if (st.status === 'failed') bg = 'var(--danger)';
        if (st.status === 'skipped') bg = 'var(--border-strong)';
        return (
          <div key={s.id} title={s.label} style={{
            width: 14, height: 4, borderRadius: 2,
            background: bg,
            animation: anim,
          }} />
        );
      })}
    </div>
  );
}

// ─── Event row in 3 styles ──────────────────────────────────

const TOOL_COLORS = {
  Read:     { bg: 'var(--bg-2)',    fg: 'var(--info)',     label: 'Read' },
  Edit:     { bg: 'var(--bg-2)',    fg: 'var(--warning)',  label: 'Edit' },
  Write:    { bg: 'var(--bg-2)',    fg: 'var(--success)',  label: 'Write' },
  Bash:     { bg: 'var(--bg-2)',    fg: 'var(--accent)',   label: 'Bash' },
  Grep:     { bg: 'var(--bg-2)',    fg: 'var(--highlight)',label: 'Grep' },
  Glob:     { bg: 'var(--bg-2)',    fg: 'var(--highlight)',label: 'Glob' },
  WebFetch: { bg: 'var(--bg-2)',    fg: 'var(--info)',     label: 'WebFetch' },
  Task:     { bg: 'var(--bg-2)',    fg: 'var(--fg-1)',     label: 'Task' },
};

// Style A — Telegram-like: cog + название + деталь
function EventRowTelegram({ event, live }) {
  if (event.kind === 'stage') return (
    <div className="fade-in" style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '6px 0', color: 'var(--fg-2)',
      fontSize: 11.5, letterSpacing: '.02em', textTransform: 'uppercase', fontWeight: 500,
    }}>
      <span style={{ flex: '0 0 auto', width: 48, fontFamily: 'var(--font-mono)', fontSize: 10.5, opacity: .7 }}>{event.ts}</span>
      <span style={{ height: 1, background: 'var(--border)', flex: 1 }} />
      <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{event.stage}</span>
      <span style={{ height: 1, background: 'var(--border)', flex: 1 }} />
    </div>
  );
  if (event.kind === 'thinking') return (
    <div className="fade-in" style={{
      display: 'flex', alignItems: 'flex-start', gap: 10,
      padding: '4px 0', color: 'var(--highlight)',
      fontStyle: 'italic', fontSize: 12.5,
    }}>
      <span style={{ flex: '0 0 auto', width: 48, fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--fg-3)', fontStyle: 'normal' }}>{event.ts}</span>
      <span style={{ flex: '0 0 auto', lineHeight: '18px' }}>🧠</span>
      <span>{event.text}</span>
    </div>
  );
  if (event.kind === 'text') return (
    <div className="fade-in" style={{
      display: 'flex', alignItems: 'flex-start', gap: 10,
      padding: '4px 0', color: 'var(--fg-0)',
      fontSize: 12.5,
    }}>
      <span style={{ flex: '0 0 auto', width: 48, fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--fg-3)' }}>{event.ts}</span>
      <span style={{ flex: '0 0 auto', lineHeight: '18px' }}>📝</span>
      <span>{event.text}</span>
    </div>
  );
  // tool
  const c = TOOL_COLORS[event.tool] || { fg: 'var(--fg-1)', label: event.tool };
  return (
    <div className="fade-in" style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '4px 0',
      fontSize: 12.5,
    }}>
      <span style={{ flex: '0 0 auto', width: 48, fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--fg-3)' }}>{event.ts}</span>
      <span style={{ color: 'var(--fg-2)', display: 'inline-flex', alignItems: 'center' }}>
        {live ? <span className="spinner" /> : <span style={{ fontSize: 11, lineHeight: 1 }}>⚙</span>}
      </span>
      <span style={{ color: c.fg, fontWeight: 600, minWidth: 60 }}>{c.label}</span>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-0)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {event.detail}
      </span>
      {event.meta && <span style={{ color: 'var(--fg-2)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>{event.meta}</span>}
      {live && <span className="caret" style={{ width: 6, height: 11 }} />}
    </div>
  );
}

// Style B — Terminal-style (monospaced log)
function EventRowTerminal({ event, live }) {
  const prefix = event.kind === 'stage' ? '━━'
    : event.kind === 'thinking' ? '··'
    : event.kind === 'text' ? '»»'
    : '$>';
  const color = event.kind === 'stage' ? 'var(--accent)'
    : event.kind === 'thinking' ? 'var(--highlight)'
    : event.kind === 'text' ? 'var(--success)'
    : event.tool === 'Bash' ? 'var(--accent)'
    : 'var(--fg-0)';

  if (event.kind === 'stage') return (
    <div className="fade-in" style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, padding: '3px 0', color: 'var(--accent)' }}>
      <span style={{ color: 'var(--fg-3)' }}>[{event.ts}]</span> <span style={{ color: 'var(--accent)' }}>━━━</span> stage: <b>{event.stage}</b> <span style={{ color: 'var(--fg-2)' }}>— {event.text}</span>
    </div>
  );
  return (
    <div className="fade-in" style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, lineHeight: 1.6, padding: '2px 0', color: 'var(--fg-0)' }}>
      <span style={{ color: 'var(--fg-3)' }}>[{event.ts}]</span>
      {' '}
      <span style={{ color }}>{prefix}</span>
      {' '}
      {event.kind === 'tool' && (
        <>
          <span style={{ color: TOOL_COLORS[event.tool]?.fg || 'var(--fg-1)' }}>{event.tool}</span>
          <span style={{ color: 'var(--fg-2)' }}> </span>
          <span>{event.detail}</span>
          {event.meta && <span style={{ color: 'var(--fg-2)' }}> {event.meta}</span>}
          {live && <span className="caret" />}
        </>
      )}
      {event.kind === 'thinking' && <span style={{ color: 'var(--highlight)', fontStyle: 'italic' }}>{event.text}</span>}
      {event.kind === 'text' && <span>{event.text}</span>}
    </div>
  );
}

// Style C — Card style (каждое событие — узкая карточка, удобно раскрывать)
function EventRowCards({ event, live }) {
  if (event.kind === 'stage') return (
    <div className="fade-in" style={{
      display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0 6px',
    }}>
      <span style={{ fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--accent)', fontWeight: 700 }}>{event.stage}</span>
      <span style={{ height: 1, background: 'var(--border)', flex: 1 }} />
      <span className="mono" style={{ color: 'var(--fg-3)', fontSize: 10.5 }}>{event.ts}</span>
    </div>
  );
  if (event.kind === 'thinking') return (
    <div className="fade-in" style={{
      background: 'var(--highlight-soft)',
      border: '1px solid var(--border)', borderLeft: '2px solid var(--highlight)',
      borderRadius: 'var(--r-md)', padding: '6px 10px',
      fontSize: 12.5, color: 'var(--highlight)', fontStyle: 'italic',
      display: 'flex', gap: 8, alignItems: 'flex-start',
    }}>
      <I.Thinking className="ico-sm" style={{ marginTop: 2, flex: '0 0 auto' }} />
      <span style={{ flex: 1 }}>{event.text}</span>
      <span className="mono dim" style={{ fontSize: 10.5, fontStyle: 'normal', flex: '0 0 auto' }}>{event.ts}</span>
    </div>
  );
  if (event.kind === 'text') return (
    <div className="fade-in" style={{
      background: 'var(--bg-2)',
      border: '1px solid var(--border)', borderLeft: '2px solid var(--success)',
      borderRadius: 'var(--r-md)', padding: '8px 10px',
      fontSize: 12.5, color: 'var(--fg-0)',
      display: 'flex', gap: 8, alignItems: 'flex-start',
    }}>
      <I.Final className="ico-sm" style={{ marginTop: 2, flex: '0 0 auto', color: 'var(--success)' }} />
      <span style={{ flex: 1 }}>{event.text}</span>
      <span className="mono dim" style={{ fontSize: 10.5, flex: '0 0 auto' }}>{event.ts}</span>
    </div>
  );
  // tool
  const c = TOOL_COLORS[event.tool] || { fg: 'var(--fg-1)' };
  return (
    <div className="fade-in" style={{
      display: 'flex', alignItems: 'center', gap: 10,
      background: 'var(--bg-1)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--r-md)',
      padding: '5px 10px',
      fontSize: 12.5,
    }}>
      <span style={{
        width: 20, height: 20, borderRadius: 5,
        background: 'var(--bg-2)',
        display: 'grid', placeItems: 'center',
        color: c.fg,
        flex: '0 0 auto',
      }}>
        {live ? <span className="spinner" /> : <ToolIcon tool={event.tool} className="ico-sm" />}
      </span>
      <span style={{ color: c.fg, fontWeight: 600, minWidth: 64, fontSize: 11.5 }}>{event.tool}</span>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--fg-0)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {event.detail}
      </span>
      {event.meta && <span style={{ color: 'var(--fg-2)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>{event.meta}</span>}
      <span className="mono dim" style={{ fontSize: 10.5 }}>{event.ts}</span>
      {live && <span className="caret" style={{ width: 5, height: 10 }} />}
    </div>
  );
}

function EventStream({ events, style = 'telegram', showThinking = true }) {
  const Row = style === 'terminal' ? EventRowTerminal : style === 'cards' ? EventRowCards : EventRowTelegram;
  const filtered = showThinking ? events : events.filter(e => e.kind !== 'thinking');
  const lastLiveIdx = filtered.map((e,i) => e.live ? i : -1).filter(i => i >= 0).pop();

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      gap: style === 'cards' ? 4 : 0,
      padding: style === 'terminal' ? '10px 14px' : '6px 12px',
      background: style === 'terminal' ? 'var(--bg-0)' : 'transparent',
      borderRadius: style === 'terminal' ? 'var(--r-md)' : 0,
      border: style === 'terminal' ? '1px solid var(--border)' : 'none',
    }}>
      {filtered.map((e, i) => (
        <Row key={i} event={e} live={!!e.live && i === lastLiveIdx} />
      ))}
    </div>
  );
}

// ─── Task row helpers ───────────────────────────────────────

function formatDuration(sec) {
  if (!sec) return '—';
  if (sec < 60) return `${Math.round(sec)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

function formatCost(usd) {
  if (!usd) return '$0.00';
  return '$' + usd.toFixed(2);
}

function RepoLabel({ repo }) {
  const parts = repo.split('/');
  return (
    <span className="mono" style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
      <span>{parts[0]}</span>
      <span style={{ color: 'var(--fg-3)' }}>/</span>
      <span style={{ color: 'var(--fg-1)' }}>{parts[1]}</span>
    </span>
  );
}

// Избранные метрики: стоимость/токены в углу, мелко
function CostCell({ task }) {
  if (task.status === 'PENDING') return <span style={{ color: 'var(--fg-3)' }}>—</span>;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 4, color: 'var(--fg-2)', fontSize: 11 }} className="tabular">
      <span>{formatCost(task.cost_usd)}</span>
      <span style={{ color: 'var(--fg-3)', fontSize: 10 }}>· {((task.tokens_in + task.tokens_out)/1000).toFixed(1)}k</span>
    </span>
  );
}

if (typeof window !== 'undefined') {
  Object.assign(window, {
    StatusChip, StageStepper, StageDots,
    EventStream, EventRowTelegram, EventRowTerminal, EventRowCards,
    formatDuration, formatCost, RepoLabel, CostCell, TOOL_COLORS,
  });
}
