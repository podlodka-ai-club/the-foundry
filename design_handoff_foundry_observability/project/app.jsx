// app.jsx — корневое приложение с 3 layout-вариантами главного экрана + 5 состояний
// Всё через design_canvas, чтобы варианты было удобно сравнивать.

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "dark",
  "layout": "table",
  "eventStyle": "telegram",
  "showThinking": true,
  "liveSimulation": true,
  "simSpeed": 1.0,
  "density": "regular"
}/*EDITMODE-END*/;

// ─── Sidebar ──────────────────────────────────────────────────
function Sidebar({ active, onNav, counts }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-logo">F</div>
        <div>
          <div className="sidebar-brand-name">Foundry</div>
          <div style={{ fontSize: 10.5, color: 'var(--fg-2)' }}>the orchestrator</div>
        </div>
      </div>

      <div className="nav-item active">
        <I.Inbox />Задачи <span className="count">{counts.total}</span>
      </div>
      <div className="nav-item">
        <I.Activity />Активные <span className="count" style={{ color: 'var(--running)' }}>{counts.running}</span>
      </div>
      <div className="nav-item">
        <I.Check />Завершённые <span className="count">{counts.done}</span>
      </div>
      <div className="nav-item">
        <I.X />Провалы <span className="count" style={{ color: 'var(--danger)' }}>{counts.failed}</span>
      </div>

      <div className="sidebar-section">Репозитории</div>
      <div className="nav-item"><I.Package />foundry-web <span className="count">4</span></div>
      <div className="nav-item"><I.Package />foundry-cli <span className="count">1</span></div>
      <div className="nav-item"><I.Package />foundry-docs <span className="count">1</span></div>

      <div className="sidebar-section">Вид</div>
      <div className="nav-item"><I.Clock />Сегодня</div>
      <div className="nav-item"><I.Clock />Эта неделя</div>

      <div style={{ flex: 1 }} />

      <div style={{
        margin: '8px 4px 4px', padding: '10px 10px',
        border: '1px solid var(--border)', borderRadius: 'var(--r-md)',
        background: 'var(--bg-0)',
      }}>
        <div style={{ fontSize: 10, letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--fg-2)', marginBottom: 6, fontWeight: 600 }}>Сегодня</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-0)' }} className="tabular">$1.11</span>
          <span style={{ fontSize: 10.5, color: 'var(--fg-2)' }}>· 129k токенов</span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 2 }}>6 задач · 5 DONE</div>
      </div>

      <div className="nav-item"><I.Settings />Настройки</div>
    </aside>
  );
}

// ─── Topbar ───────────────────────────────────────────────────
function Topbar({ tweaks, setTweak }) {
  return (
    <div className="topbar">
      <div className="topbar-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <I.Inbox style={{ color: 'var(--accent)' }} />
        Задачи
      </div>
      <span className="topbar-crumb">все репозитории</span>
      <div className="topbar-spacer" />
      <div className="search">
        <I.Search />
        <input placeholder="Искать…" />
        <span className="kbd">⌘K</span>
      </div>
      <button
        className="topbar-btn"
        onClick={() => setTweak('theme', tweaks.theme === 'dark' ? 'light' : 'dark')}
        title="Переключить тему"
      >
        {tweaks.theme === 'dark' ? <I.Sun className="ico-sm" /> : <I.Moon className="ico-sm" />}
      </button>
      <button className="topbar-btn primary"><I.Plus className="ico-sm" />Run</button>
    </div>
  );
}

// ─── Toolbar (filters) ────────────────────────────────────────
function FilterBar({ filter, setFilter, counts }) {
  return (
    <div className="toolbar">
      <button className={`filter-pill ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>Все <span className="dim">{counts.total}</span></button>
      <button className={`filter-pill ${filter === 'RUNNING' ? 'active' : ''}`} onClick={() => setFilter('RUNNING')}>
        <span className="dot dot-running" />Активные <span className="dim">{counts.running}</span>
      </button>
      <button className={`filter-pill ${filter === 'DONE' ? 'active' : ''}`} onClick={() => setFilter('DONE')}>Завершённые <span className="dim">{counts.done}</span></button>
      <button className={`filter-pill ${filter === 'FAILED' ? 'active' : ''}`} onClick={() => setFilter('FAILED')}>Провалы <span className="dim">{counts.failed}</span></button>
      <button className={`filter-pill ${filter === 'PENDING' ? 'active' : ''}`} onClick={() => setFilter('PENDING')}>Ожидают <span className="dim">{counts.pending}</span></button>
      <div style={{ flex: 1 }} />
      <button className="filter-pill"><I.Sort className="ico-sm" />updated_at ↓</button>
      <button className="filter-pill"><I.Filter className="ico-sm" />Фильтры</button>
    </div>
  );
}

// ─── Column headers (только для table-layout) ────────────────
function TableHeader() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '22px 92px 1fr 240px 80px 80px 24px',
      alignItems: 'center',
      gap: 14,
      padding: '7px 20px 7px 22px',
      fontSize: 10, fontWeight: 600, letterSpacing: '.1em', textTransform: 'uppercase',
      color: 'var(--fg-2)',
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-0)',
    }}>
      <span />
      <span>Статус</span>
      <span>Задача</span>
      <span style={{ textAlign: 'left' }}>Стадии</span>
      <span style={{ justifySelf: 'end' }}>Время</span>
      <span style={{ justifySelf: 'end' }}>$/ток.</span>
      <span />
    </div>
  );
}

// ─── Empty & Error states ─────────────────────────────────────
function EmptyState() {
  return (
    <div className="state-block">
      <div className="state-icon"><I.Inbox className="ico-lg" /></div>
      <h3>Пока нет задач</h3>
      <p>Когда вы запустите <span className="mono" style={{ color: 'var(--fg-0)' }}>foundry run</span> или добавите GitHub-issue с лейблом <span className="mono" style={{ color: 'var(--accent)' }}>foundry-run</span>, она появится здесь.</p>
      <div style={{ display: 'flex', gap: 8, marginTop: 18 }}>
        <button className="topbar-btn primary"><I.Plus className="ico-sm" />Создать задачу</button>
        <button className="topbar-btn">Открыть документацию</button>
      </div>
    </div>
  );
}

// ─── Activity heatmap / sparkline для топ-бара (decor) ────────
function MiniSpark() {
  const bars = [3, 5, 2, 7, 4, 9, 6, 8, 5, 10, 7, 4, 6, 11, 8];
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 20 }}>
      {bars.map((h, i) => (
        <div key={i} style={{
          width: 3, height: `${h * 1.8}px`,
          background: i === bars.length - 1 ? 'var(--running)' : 'var(--border-strong)',
          borderRadius: 1,
        }} />
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Screens: 3 варианта главного экрана
// ─────────────────────────────────────────────────────────────
function ScreenTable({ tweaks, setTweak, expandedId, setExpandedId, tasks, events }) {
  const [filter, setFilter] = React.useState('all');
  const counts = React.useMemo(() => ({
    total: tasks.length,
    running: tasks.filter(t => t.status === 'RUNNING').length,
    done: tasks.filter(t => t.status === 'DONE').length,
    failed: tasks.filter(t => t.status === 'FAILED').length,
    pending: tasks.filter(t => t.status === 'PENDING').length,
  }), [tasks]);
  const filtered = filter === 'all' ? tasks : tasks.filter(t => t.status === filter);

  return (
    <div className="app-shell">
      <Sidebar counts={counts} />
      <div className="main">
        <Topbar tweaks={tweaks} setTweak={setTweak} />
        <FilterBar filter={filter} setFilter={setFilter} counts={counts} />
        <TableHeader />
        {filtered.map(t => (
          <TaskRowLinear
            key={t.id}
            task={t}
            expanded={expandedId === t.id}
            onToggle={() => setExpandedId(expandedId === t.id ? null : t.id)}
            eventStyle={tweaks.eventStyle}
            showThinking={tweaks.showThinking}
            events={t.id === 'tsk_7f2a9c' ? events : []}
          />
        ))}
      </div>
    </div>
  );
}

function ScreenCards({ tweaks, setTweak, expandedId, setExpandedId, tasks, events }) {
  const [filter, setFilter] = React.useState('all');
  const counts = React.useMemo(() => ({
    total: tasks.length,
    running: tasks.filter(t => t.status === 'RUNNING').length,
    done: tasks.filter(t => t.status === 'DONE').length,
    failed: tasks.filter(t => t.status === 'FAILED').length,
    pending: tasks.filter(t => t.status === 'PENDING').length,
  }), [tasks]);
  const filtered = filter === 'all' ? tasks : tasks.filter(t => t.status === filter);

  return (
    <div className="app-shell">
      <Sidebar counts={counts} />
      <div className="main">
        <Topbar tweaks={tweaks} setTweak={setTweak} />
        <FilterBar filter={filter} setFilter={setFilter} counts={counts} />
        <div style={{ padding: '16px 20px 40px' }}>
          {filtered.map(t => (
            <TaskCard
              key={t.id}
              task={t}
              expanded={expandedId === t.id}
              onToggle={() => setExpandedId(expandedId === t.id ? null : t.id)}
              eventStyle={tweaks.eventStyle}
              showThinking={tweaks.showThinking}
              events={t.id === 'tsk_7f2a9c' ? events : []}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ScreenCompact({ tweaks, setTweak, expandedId, setExpandedId, tasks, events }) {
  const [filter, setFilter] = React.useState('all');
  const counts = React.useMemo(() => ({
    total: tasks.length,
    running: tasks.filter(t => t.status === 'RUNNING').length,
    done: tasks.filter(t => t.status === 'DONE').length,
    failed: tasks.filter(t => t.status === 'FAILED').length,
    pending: tasks.filter(t => t.status === 'PENDING').length,
  }), [tasks]);
  const filtered = filter === 'all' ? tasks : tasks.filter(t => t.status === filter);

  return (
    <div className="app-shell">
      <Sidebar counts={counts} />
      <div className="main">
        <Topbar tweaks={tweaks} setTweak={setTweak} />
        <FilterBar filter={filter} setFilter={setFilter} counts={counts} />
        <div style={{
          display: 'grid',
          gridTemplateColumns: '18px 14px 68px 1fr 140px 56px 56px',
          alignItems: 'center',
          gap: 10,
          padding: '6px 20px 6px 14px',
          fontSize: 10, fontWeight: 600, letterSpacing: '.1em', textTransform: 'uppercase',
          color: 'var(--fg-2)',
          borderBottom: '1px solid var(--border)',
        }}>
          <span /><span /><span>id</span><span>заголовок</span><span>стадии</span><span style={{ textAlign: 'right' }}>время</span><span style={{ textAlign: 'right' }}>$</span>
        </div>
        {filtered.map(t => (
          <TaskRowCompact
            key={t.id}
            task={t}
            expanded={expandedId === t.id}
            onToggle={() => setExpandedId(expandedId === t.id ? null : t.id)}
            eventStyle={tweaks.eventStyle}
            showThinking={tweaks.showThinking}
            events={t.id === 'tsk_7f2a9c' ? events : []}
          />
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Симуляция live-потока событий: периодически «добавляет» событий
// ─────────────────────────────────────────────────────────────
function useLiveEvents(enabled, speed) {
  const FULL = EVENTS_412;
  const [count, setCount] = React.useState(16);

  React.useEffect(() => {
    if (!enabled) return;
    const interval = 1800 / speed;
    const t = setInterval(() => {
      setCount(c => {
        if (c >= FULL.length) return 16; // loop
        return c + 1;
      });
    }, interval);
    return () => clearInterval(t);
  }, [enabled, speed]);

  // клонируем и помечаем последнее событие как live
  const visible = FULL.slice(0, count).map((e, i, arr) => {
    if (i === arr.length - 1 && enabled && e.kind === 'tool') return { ...e, live: true };
    return e;
  });
  return [visible, count];
}

// ─────────────────────────────────────────────────────────────
// Главный App: design_canvas с 3 вариантами layout'а + 3 состояния
// ─────────────────────────────────────────────────────────────
function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // применяем theme
  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', tweaks.theme);
  }, [tweaks.theme]);

  const [expandedId, setExpandedId] = React.useState('tsk_7f2a9c');
  const [events, count] = useLiveEvents(tweaks.liveSimulation, tweaks.simSpeed);

  // Моделируем состояние «пусто» — пустой список задач
  const emptyTasks = [];

  // Error-состояние: только проваленная задача, раскрытая
  const errorTasks = TASKS.filter(t => t.status === 'FAILED');

  return (
    <>
      <DesignCanvas>
        <DCSection id="main" title="Главный экран · 3 варианта" subtitle="Список задач с раскрытыми деталями. Dark/light + layout/event-style через Tweaks">
          <DCArtboard id="table" label="A · Табличный (Linear-like, плотная сетка)" width={1360} height={1040}>
            <ScreenTable
              tweaks={tweaks} setTweak={setTweak}
              expandedId={expandedId} setExpandedId={setExpandedId}
              tasks={TASKS} events={events}
            />
          </DCArtboard>

          <DCArtboard id="cards" label="B · Карточки (просторный, для фокусного чтения)" width={1360} height={1280}>
            <ScreenCards
              tweaks={tweaks} setTweak={setTweak}
              expandedId={expandedId} setExpandedId={setExpandedId}
              tasks={TASKS} events={events}
            />
          </DCArtboard>

          <DCArtboard id="compact" label="C · Компактный (mono, log-style density)" width={1360} height={960}>
            <ScreenCompact
              tweaks={tweaks} setTweak={setTweak}
              expandedId={expandedId} setExpandedId={setExpandedId}
              tasks={TASKS} events={events}
            />
          </DCArtboard>
        </DCSection>

        <DCSection id="states" title="Состояния" subtitle="Пусто, раскрытая ошибка с traceback">
          <DCArtboard id="empty" label="Пусто — нет ни одной задачи" width={1360} height={640}>
            <ScreenTable
              tweaks={tweaks} setTweak={setTweak}
              expandedId={null} setExpandedId={() => {}}
              tasks={emptyTasks} events={[]}
            />
            <div style={{ position: 'relative', top: -400 }}>
              <EmptyState />
            </div>
          </DCArtboard>

          <DCArtboard id="error" label="Провал задачи — traceback + retry" width={1360} height={900}>
            <ScreenTable
              tweaks={tweaks} setTweak={setTweak}
              expandedId="tsk_9a4c21" setExpandedId={() => {}}
              tasks={errorTasks} events={[]}
            />
          </DCArtboard>
        </DCSection>

        <DCSection id="stream" title="Поток событий агента · крупно" subtitle="Как именно показываем Read/Edit/Bash/Thinking/Final. 3 стиля рендера.">
          <DCArtboard id="telegram" label="Telegram-style (⚙ Tool: detail)" width={720} height={640}>
            <div style={{ background: 'var(--bg-0)', padding: 16, height: '100%' }}>
              <StreamHeader title="⚙ Telegram-style" desc="как в myagent: иконка-шестерёнка + tool + деталь" />
              <EventStream events={events} style="telegram" showThinking={tweaks.showThinking} />
            </div>
          </DCArtboard>
          <DCArtboard id="terminal" label="Terminal-style (log-like)" width={720} height={640}>
            <div style={{ background: 'var(--bg-0)', padding: 16, height: '100%' }}>
              <StreamHeader title="$> Terminal-style" desc="моноширинный лог с префиксами и живым caret'ом" />
              <EventStream events={events} style="terminal" showThinking={tweaks.showThinking} />
            </div>
          </DCArtboard>
          <DCArtboard id="cards-stream" label="Card-style (каждое событие — строка-пилюля)" width={720} height={640}>
            <div style={{ background: 'var(--bg-0)', padding: 16, height: '100%' }}>
              <StreamHeader title="▢ Cards" desc="узкие карточки с иконкой инструмента — легко кликать" />
              <EventStream events={events} style="cards" showThinking={tweaks.showThinking} />
            </div>
          </DCArtboard>
        </DCSection>
      </DesignCanvas>

      <TweaksPanel>
        <TweakSection label="Тема и плотность" />
        <TweakRadio label="Тема" value={tweaks.theme} options={['dark', 'light']} onChange={(v) => setTweak('theme', v)} />

        <TweakSection label="Поток событий" />
        <TweakRadio label="Стиль" value={tweaks.eventStyle} options={['telegram', 'terminal', 'cards']} onChange={(v) => setTweak('eventStyle', v)} />
        <TweakToggle label="Показывать thinking" value={tweaks.showThinking} onChange={(v) => setTweak('showThinking', v)} />

        <TweakSection label="Симуляция" />
        <TweakToggle label="Live-поток" value={tweaks.liveSimulation} onChange={(v) => setTweak('liveSimulation', v)} />
        <TweakSlider label="Скорость" value={tweaks.simSpeed} min={0.25} max={4} step={0.25} unit="×" onChange={(v) => setTweak('simSpeed', v)} />

        <TweakSection label="Стат. симуляции" />
        <div style={{ fontSize: 10.5, color: 'rgba(41,38,27,.6)', lineHeight: 1.5 }}>
          События: <b>{count}/{EVENTS_412.length}</b><br/>
          Обновляется каждые {Math.round(1800/tweaks.simSpeed)} мс
        </div>
      </TweaksPanel>
    </>
  );
}

function StreamHeader({ title, desc }) {
  return (
    <div style={{ marginBottom: 12, paddingBottom: 10, borderBottom: '1px solid var(--border)' }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-0)' }}>{title}</div>
      <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 2 }}>{desc}</div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
