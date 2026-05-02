// task-row.jsx — карточка/строка задачи в трёх layout'ах
// + TaskDetails (раскрытая панель)

// ─── Стрелка-раскрыватель ──────────────────────────────────
function ExpandArrow({ open }) {
  return (
    <I.Chevron className="ico-sm" style={{
      transform: open ? 'rotate(90deg)' : 'rotate(0)',
      transition: 'transform .18s cubic-bezier(.2,.7,.3,1)',
      color: 'var(--fg-2)',
      flexShrink: 0,
    }} />
  );
}

// ─────────────────────────────────────────────────────────────
// Layout A — строка таблицы, inline-раскрытие (как GitHub Actions / Linear)
// ─────────────────────────────────────────────────────────────
function TaskRowLinear({ task, expanded, onToggle, eventStyle, showThinking, events }) {
  const isRunning = task.status === 'RUNNING';
  return (
    <div style={{ borderBottom: '1px solid var(--border-soft)' }}>
      <div
        onClick={onToggle}
        className={isRunning ? 'selected-bar' : ''}
        style={{
          display: 'grid',
          gridTemplateColumns: '22px 92px 1fr 240px 80px 80px 24px',
          alignItems: 'center',
          gap: 14,
          padding: '11px 20px 11px 22px',
          cursor: 'pointer',
          background: expanded ? 'var(--bg-1)' : 'transparent',
          transition: 'background .12s',
        }}
        onMouseEnter={(e) => { if (!expanded) e.currentTarget.style.background = 'var(--bg-1)'; }}
        onMouseLeave={(e) => { if (!expanded) e.currentTarget.style.background = 'transparent'; }}
      >
        <ExpandArrow open={expanded} />

        <StatusChip status={task.status} />

        <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div className="ellipsis" style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-0)' }}>
            {task.issue_title}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--fg-2)', fontSize: 11.5 }}>
            <RepoLabel repo={task.repo} />
            <span style={{ color: 'var(--fg-3)' }}>·</span>
            <span className="mono" style={{ color: 'var(--accent)' }}>#{task.issue_number}</span>
            <span style={{ color: 'var(--fg-3)' }}>·</span>
            <span>{task.started_at}</span>
            {task.attempts > 1 && <>
              <span style={{ color: 'var(--fg-3)' }}>·</span>
              <span style={{ color: 'var(--warning)' }}>попытка {task.attempts}</span>
            </>}
          </div>
        </div>

        <StageStepper stages={task.stages} size="sm" showLabels={false} />

        <span className="tabular" style={{ fontSize: 12, color: 'var(--fg-1)', justifySelf: 'end' }}>
          {isRunning ? <><span className="dot dot-running" style={{ marginRight: 6, width: 5, height: 5 }} />{formatDuration(task.duration_sec)}</> : formatDuration(task.duration_sec)}
        </span>

        <span style={{ justifySelf: 'end' }}>
          <CostCell task={task} />
        </span>

        {task.pr_url ? (
          <a href="#" onClick={(e) => e.stopPropagation()} style={{ color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 11.5 }} className="mono" title={task.pr_url}>
            <I.External className="ico-sm" />
          </a>
        ) : <span />}
      </div>

      {expanded && <TaskDetails task={task} events={events} eventStyle={eventStyle} showThinking={showThinking} />}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Layout B — карточка (более просторная, для среднего режима)
// ─────────────────────────────────────────────────────────────
function TaskCard({ task, expanded, onToggle, eventStyle, showThinking, events }) {
  const isRunning = task.status === 'RUNNING';
  return (
    <div style={{
      background: 'var(--bg-1)',
      border: `1px solid ${isRunning ? 'var(--running)' : 'var(--border)'}`,
      borderRadius: 'var(--r-lg)',
      marginBottom: 10,
      overflow: 'hidden',
      boxShadow: isRunning ? '0 0 0 3px var(--running-soft)' : 'none',
      transition: 'box-shadow .3s',
    }}>
      <div
        onClick={onToggle}
        style={{ padding: '12px 16px', cursor: 'pointer' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <StatusChip status={task.status} />
          <RepoLabel repo={task.repo} />
          <span style={{ color: 'var(--fg-3)' }}>·</span>
          <a onClick={e => e.stopPropagation()} className="mono" style={{ color: 'var(--accent)', fontSize: 12 }}>#{task.issue_number}</a>
          <span style={{ color: 'var(--fg-3)' }}>·</span>
          <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>{task.started_at}</span>
          <span style={{ flex: 1 }} />
          <span className="tabular" style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
            {formatDuration(task.duration_sec)}
          </span>
          <span style={{ color: 'var(--fg-3)' }}>·</span>
          <CostCell task={task} />
          <ExpandArrow open={expanded} />
        </div>
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--fg-0)', marginBottom: 14, letterSpacing: '-.005em' }}>
          {task.issue_title}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ paddingLeft: 4 }}>
            <StageStepper stages={task.stages} size="md" showLabels={true} />
          </div>
          <div style={{ flex: 1, height: 18 }} />
          {task.pr_url && (
            <a onClick={e => e.stopPropagation()} style={{ fontSize: 11.5, color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', gap: 4 }} className="mono" title={task.pr_url}>
              PR #{task.pr_number} <I.External className="ico-sm" />
            </a>
          )}
        </div>
      </div>
      {expanded && <TaskDetails task={task} events={events} eventStyle={eventStyle} showThinking={showThinking} />}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Layout C — компактная строка (density mode, как k9s/logs)
// ─────────────────────────────────────────────────────────────
function TaskRowCompact({ task, expanded, onToggle, eventStyle, showThinking, events }) {
  const isRunning = task.status === 'RUNNING';
  let statusGlyph;
  if (isRunning) statusGlyph = <span className="dot dot-running" style={{ width: 7, height: 7 }} />;
  else if (task.status === 'DONE') statusGlyph = <I.Check className="ico-sm" style={{ color: 'var(--success)' }} />;
  else if (task.status === 'FAILED') statusGlyph = <I.X className="ico-sm" style={{ color: 'var(--danger)' }} />;
  else statusGlyph = <span className="dot dot-pending" style={{ width: 7, height: 7 }} />;

  return (
    <div style={{ borderBottom: '1px solid var(--border-soft)' }}>
      <div
        onClick={onToggle}
        style={{
          display: 'grid',
          gridTemplateColumns: '18px 14px 68px 1fr 140px 56px 56px',
          alignItems: 'center',
          gap: 10,
          padding: '6px 20px 6px 14px',
          cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          background: expanded ? 'var(--bg-1)' : 'transparent',
          transition: 'background .12s',
        }}
        onMouseEnter={(e) => { if (!expanded) e.currentTarget.style.background = 'var(--bg-1)'; }}
        onMouseLeave={(e) => { if (!expanded) e.currentTarget.style.background = 'transparent'; }}
      >
        <span style={{ color: 'var(--fg-3)' }}>{expanded ? '▾' : '▸'}</span>
        {statusGlyph}
        <span style={{ color: 'var(--accent)' }}>#{task.issue_number}</span>
        <span className="ellipsis" style={{ fontFamily: 'var(--font-sans)', color: 'var(--fg-0)' }}>{task.issue_title}</span>
        <StageDots stages={task.stages} />
        <span className="tabular" style={{ color: 'var(--fg-2)', fontSize: 11, textAlign: 'right' }}>
          {formatDuration(task.duration_sec)}
        </span>
        <span className="tabular" style={{ color: 'var(--fg-2)', fontSize: 11, textAlign: 'right' }}>
          {task.cost_usd ? '$' + task.cost_usd.toFixed(2) : '—'}
        </span>
      </div>
      {expanded && <TaskDetails task={task} events={events} eventStyle={eventStyle} showThinking={showThinking} />}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Раскрытая панель деталей задачи — таймлайн кликабельный,
// под ним показываются детали выбранной стадии (вход / события / выход)
// ─────────────────────────────────────────────────────────────
function TaskDetails({ task, events, eventStyle, showThinking }) {
  // Определяем стадию по умолчанию: running > failed > последняя done > первая
  const defaultStage = React.useMemo(() => {
    for (const s of STAGES) {
      if (task.stages[s.id]?.status === 'running') return s.id;
    }
    for (const s of STAGES) {
      if (task.stages[s.id]?.status === 'failed') return s.id;
    }
    let last = null;
    for (const s of STAGES) {
      if (task.stages[s.id]?.status === 'done') last = s.id;
    }
    return last || STAGES[0].id;
  }, [task]);

  const [selectedStage, setSelectedStage] = React.useState(defaultStage);
  React.useEffect(() => { setSelectedStage(defaultStage); }, [defaultStage]);

  const stage = task.stages[selectedStage] || { status: 'pending' };
  const stageMeta = STAGES.find(s => s.id === selectedStage);
  const stageEvents = (events || []).filter(e => e.stage === selectedStage);
  const isAgentStage = selectedStage === 'agent_plan' || selectedStage === 'agent_implement';

  return (
    <div style={{
      background: 'var(--bg-0)',
      borderTop: '1px solid var(--border)',
      padding: '16px 24px 18px',
      display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      {/* Meta header */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 16, alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {task.issue_body && (
            <div style={{ fontSize: 13, color: 'var(--fg-1)', lineHeight: 1.55, textWrap: 'pretty', maxWidth: 720 }}>
              {task.issue_body}
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
            {task.issue_labels?.map(l => (
              <span key={l} style={{
                padding: '1px 7px', borderRadius: 999, border: '1px solid var(--border)',
                fontSize: 11, color: 'var(--fg-2)',
              }}>{l}</span>
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 4, fontSize: 11.5, color: 'var(--fg-2)', flexWrap: 'wrap' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }} className="mono">
              <I.User className="ico-sm" />{task.issue_author}
            </span>
            {task.branch && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }} className="mono">
                <I.Branch className="ico-sm" />{task.branch}
              </span>
            )}
            {task.worktree && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }} className="mono">
                <I.Folder className="ico-sm" />{task.worktree}
              </span>
            )}
            <a className="mono" style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--fg-1)' }}>
              <I.GitHub className="ico-sm" />
              github.com/{task.repo}/issues/{task.issue_number}
              <I.External className="ico-sm" style={{ opacity: .5 }} />
            </a>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {task.status === 'RUNNING' && (
            <button className="topbar-btn"><I.Cancel className="ico-sm" />Отменить</button>
          )}
          {task.status === 'FAILED' && (
            <button className="topbar-btn primary"><I.Retry className="ico-sm" />Retry</button>
          )}
          {task.pr_url && (
            <button className="topbar-btn"><I.External className="ico-sm" />PR #{task.pr_number}</button>
          )}
        </div>
      </div>

      {/* Stage timeline — кликабельный stepper */}
      <div className="card" style={{ padding: '16px 22px 8px', position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
          <span style={{ fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--fg-2)', fontWeight: 600 }}>Таймлайн стадий</span>
          <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
            кликните на стадию, чтобы увидеть детали
          </span>
        </div>
        <div style={{ paddingLeft: 4, paddingBottom: 4 }}>
          <StageStepper
            stages={task.stages}
            size="lg"
            showLabels
            onStageClick={setSelectedStage}
            selectedStage={selectedStage}
          />
        </div>
      </div>

      {/* Stage details panel */}
      <StageDetailPanel
        task={task}
        stageId={selectedStage}
        stageMeta={stageMeta}
        stage={stage}
        events={stageEvents}
        allEvents={events}
        eventStyle={eventStyle}
        showThinking={showThinking}
        isAgentStage={isAgentStage}
      />

      {/* Error block — всегда показываем если есть, вне зависимости от выбранной стадии */}
      {task.error && selectedStage !== task.error.stage && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8, background: 'var(--danger-soft)' }}>
            <I.X className="ico-sm" style={{ color: 'var(--danger)' }} />
            <span style={{ fontSize: 12, color: 'var(--fg-0)' }}>
              Задача упала на стадии <span className="mono" style={{ color: 'var(--danger)', fontWeight: 600 }}>{task.error.stage}</span>
            </span>
            <span style={{ flex: 1 }} />
            <button onClick={() => setSelectedStage(task.error.stage)} style={{ fontSize: 11, color: 'var(--accent)' }}>
              Посмотреть детали →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Детали одной стадии: шапка с агентом, время/стоимость,
// три блока — вход / события / выход, + композер «задать вопрос»
// ─────────────────────────────────────────────────────────────
function StageDetailPanel({ task, stageId, stageMeta, stage, events, eventStyle, showThinking, isAgentStage }) {
  const isPending = stage.status === 'pending' || !stage.status;
  const isSkipped = stage.status === 'skipped';
  const isRunning = stage.status === 'running';
  const isFailed  = stage.status === 'failed';

  if (isPending || isSkipped) {
    return (
      <div className="card" style={{ padding: '22px 24px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          background: 'var(--bg-2)',
          display: 'grid', placeItems: 'center',
          color: 'var(--fg-3)',
          border: isSkipped ? '1px dashed var(--border-strong)' : 'none',
        }}>
          <I.Clock className="ico-sm" />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-1)' }}>
            Стадия <span className="mono" style={{ color: 'var(--fg-0)' }}>{stageMeta.label}</span> — {isSkipped ? 'пропущена' : 'ещё не выполнялась'}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--fg-2)', marginTop: 2 }}>
            {isSkipped ? 'Предыдущая стадия провалилась, поэтому эта не запускалась.' : 'Начнётся после завершения предыдущих стадий.'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      {/* Шапка стадии */}
      <div style={{
        padding: '12px 18px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 12,
        background: isRunning ? 'var(--running-soft)' : isFailed ? 'var(--danger-soft)' : 'var(--bg-1)',
      }}>
        <span style={{
          fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', fontWeight: 700,
          color: isRunning ? 'var(--running)' : isFailed ? 'var(--danger)' : 'var(--success)',
        }}>
          {stageMeta.title}
        </span>
        <span className="mono" style={{ color: 'var(--fg-3)', fontSize: 11 }}>·</span>
        {isRunning && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--running)' }}>
            <span className="spinner" />идёт сейчас
          </span>
        )}
        {stage.status === 'done' && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--success)' }}>
            <I.Check className="ico-sm" />завершено
          </span>
        )}
        {isFailed && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--danger)' }}>
            <I.X className="ico-sm" />провал
          </span>
        )}
        <span style={{ flex: 1 }} />

        {/* Плашка агента */}
        {stage.agent && (
          <AgentBadge agent={stage.agent} />
        )}

        {/* Метрики стадии — мелко */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11, color: 'var(--fg-2)' }} className="tabular">
          {stage.duration != null && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <I.Clock className="ico-sm" />{formatDuration(stage.duration)}
            </span>
          )}
          {stage.cost > 0 && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              ${stage.cost.toFixed(2)}
            </span>
          )}
          {stage.tokens_in && (
            <span style={{ color: 'var(--fg-3)' }}>
              {((stage.tokens_in + stage.tokens_out) / 1000).toFixed(1)}k ток.
            </span>
          )}
        </div>
      </div>

      {/* Содержимое: вход → события → выход */}
      <div style={{ display: 'grid', gridTemplateColumns: isAgentStage ? '1fr 1.4fr 1fr' : '1fr 1fr', minHeight: 240 }}>
        {/* Вход */}
        <StageSubblock title="Вход" icon={<I.Chevron className="ico-sm" style={{ transform: 'rotate(90deg)' }} />}>
          <StageIO data={stage.input} />
        </StageSubblock>

        {/* Поток событий стадии — только для агентских */}
        {isAgentStage && (
          <StageSubblock
            title="Поток событий"
            icon={<I.Activity className="ico-sm" style={{ color: 'var(--accent)' }} />}
            trailing={isRunning ? <span style={{ color: 'var(--running)', fontSize: 10.5, display: 'inline-flex', alignItems: 'center', gap: 4 }}><span className="dot dot-running" style={{ width: 5, height: 5 }} />live</span> : <span className="mono dim" style={{ fontSize: 10.5 }}>{events.length}</span>}
            noPad
          >
            {events.length > 0 ? (
              <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                <EventStream events={events} style={eventStyle} showThinking={showThinking} />
              </div>
            ) : (
              <div style={{ padding: 16, fontSize: 11.5, color: 'var(--fg-3)' }}>
                Пока нет событий
              </div>
            )}
          </StageSubblock>
        )}

        {/* Выход */}
        <StageSubblock title="Выход" icon={<I.Chevron className="ico-sm" />}>
          <StageIO data={stage.output} />
        </StageSubblock>
      </div>

      {/* Traceback при проваленной стадии */}
      {isFailed && task.error && task.error.stage === stageId && (
        <div style={{ padding: '0 14px 14px' }}>
          <pre className="trace">{task.error.trace.join('\n')}</pre>
        </div>
      )}

      {/* Композер «задать вопрос модели» — только для агентских стадий */}
      {isAgentStage && stage.agent && <AskAgentComposer agent={stage.agent} stageMeta={stageMeta} />}
    </div>
  );
}

// ─── Sub-block с заголовком
function StageSubblock({ title, icon, trailing, children, noPad }) {
  return (
    <div style={{ borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      <div style={{
        padding: '8px 14px',
        borderBottom: '1px solid var(--border-soft)',
        display: 'flex', alignItems: 'center', gap: 6,
        fontSize: 10, letterSpacing: '.08em', textTransform: 'uppercase', fontWeight: 600,
        color: 'var(--fg-2)',
        flexShrink: 0,
      }}>
        {icon}
        <span>{title}</span>
        <span style={{ flex: 1 }} />
        {trailing}
      </div>
      <div style={{ padding: noPad ? 0 : '10px 14px', flex: 1, overflow: 'hidden', minHeight: 0 }}>
        {children}
      </div>
    </div>
  );
}

// ─── Отрисовка вход/выход по типу данных
function StageIO({ data }) {
  if (!data) return <span className="dim" style={{ fontSize: 11.5 }}>—</span>;

  if (data.kind === 'kv') {
    return (
      <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', fontSize: 11.5 }}>
        {data.items.map(([k, v], i) => (
          <React.Fragment key={i}>
            <dt className="mono" style={{ color: 'var(--fg-3)' }}>{k}</dt>
            <dd className="mono" style={{ color: 'var(--fg-0)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v}</dd>
          </React.Fragment>
        ))}
      </dl>
    );
  }

  if (data.kind === 'files') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {data.label && <div style={{ fontSize: 11, color: 'var(--fg-2)', marginBottom: 4 }}>{data.label}</div>}
        {data.items.map((f, i) => (
          <div key={i} className="mono" style={{ fontSize: 11.5, color: 'var(--fg-1)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <I.Folder className="ico-sm" style={{ color: 'var(--fg-3)' }} />{f}
          </div>
        ))}
      </div>
    );
  }

  if (data.kind === 'text') {
    return (
      <div>
        {data.label && <div style={{ fontSize: 10.5, color: 'var(--fg-3)', marginBottom: 4, letterSpacing: '.06em', textTransform: 'uppercase' }}>{data.label}</div>}
        <div style={{ fontSize: 12.5, color: 'var(--fg-0)', lineHeight: 1.55, textWrap: 'pretty' }}>{data.text}</div>
      </div>
    );
  }

  if (data.kind === 'error') {
    return (
      <div>
        <div style={{ fontSize: 11.5, color: 'var(--danger)', marginBottom: 4 }}>{data.label}</div>
        <div className="mono" style={{ fontSize: 11.5, color: 'var(--fg-1)' }}>{data.text}</div>
      </div>
    );
  }

  if (data.kind === 'pending') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--fg-2)', fontSize: 11.5 }}>
        <span className="spinner" />
        {data.label || 'в процессе…'}
      </div>
    );
  }

  return null;
}

// ─── Плашка агента
function AgentBadge({ agent }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '3px 8px 3px 4px',
      borderRadius: 999,
      background: 'var(--bg-0)',
      border: '1px solid var(--border)',
      fontSize: 11,
    }}>
      <span style={{
        width: 18, height: 18, borderRadius: '50%',
        background: 'var(--accent)',
        display: 'grid', placeItems: 'center',
        color: '#fff',
      }}>
        <I.Spark className="ico-sm" style={{ width: 10, height: 10 }} />
      </span>
      <span style={{ color: 'var(--fg-0)', fontWeight: 500 }}>{agent.name}</span>
      <span style={{ color: 'var(--fg-3)' }}>·</span>
      <span className="mono" style={{ color: 'var(--fg-1)', fontSize: 10.5 }}>{agent.model}</span>
    </div>
  );
}

// ─── Композер вопроса модели
function AskAgentComposer({ agent, stageMeta }) {
  const [open, setOpen] = React.useState(false);
  const [value, setValue] = React.useState('');

  if (!open) {
    return (
      <div style={{
        padding: '10px 14px',
        borderTop: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'var(--bg-1)',
      }}>
        <I.Thinking className="ico-sm" style={{ color: 'var(--highlight)' }} />
        <span style={{ fontSize: 12, color: 'var(--fg-1)' }}>
          Уточнить у <span style={{ fontWeight: 500 }}>{agent.name}</span> — что именно сделано и почему
        </span>
        <span style={{ flex: 1 }} />
        <button className="topbar-btn" onClick={() => setOpen(true)}>
          Задать вопрос <span className="kbd" style={{ marginLeft: 4 }}>/</span>
        </button>
      </div>
    );
  }

  return (
    <div style={{
      padding: '12px 14px',
      borderTop: '1px solid var(--border)',
      background: 'var(--bg-1)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <I.Thinking className="ico-sm" style={{ color: 'var(--highlight)' }} />
        <span style={{ fontSize: 11, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--fg-2)', fontWeight: 600 }}>
          Спросить у агента
        </span>
        <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>·</span>
        <AgentBadge agent={agent} />
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
          контекст стадии <span className="mono" style={{ color: 'var(--fg-1)' }}>{stageMeta.label}</span> прикладывается автоматически
        </span>
      </div>
      <div style={{
        border: '1px solid var(--border-strong)',
        borderRadius: 'var(--r-md)',
        background: 'var(--bg-0)',
        padding: 10,
      }}>
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          autoFocus
          placeholder="Почему ты решил положить EventBus в отдельный модуль вместо api/?"
          rows={3}
          style={{
            width: '100%', background: 'transparent', border: 0, outline: 0,
            resize: 'none', color: 'var(--fg-0)',
            font: 'inherit', fontSize: 13, lineHeight: 1.5,
          }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, paddingTop: 8, borderTop: '1px solid var(--border-soft)' }}>
          <span className="hint">⌘+Enter — отправить</span>
          <span style={{ flex: 1 }} />
          <button className="topbar-btn" onClick={() => { setOpen(false); setValue(''); }}>Отмена</button>
          <button className="topbar-btn primary" disabled={!value.trim()} style={{ opacity: value.trim() ? 1 : .5 }}>
            Отправить
          </button>
        </div>
      </div>
    </div>
  );
}

if (typeof window !== 'undefined') {
  Object.assign(window, { TaskRowLinear, TaskCard, TaskRowCompact, TaskDetails, ExpandArrow });
}
