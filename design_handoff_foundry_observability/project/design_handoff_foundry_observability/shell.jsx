// shell.jsx — Sidebar, Topbar, FilterBar, TableHeader, EmptyState
// Shell-компоненты главного экрана. Без design_canvas / tweaks-panel.

function Sidebar({ counts }) {
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

function Topbar({ theme, onToggleTheme }) {
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
      <button className="topbar-btn" onClick={onToggleTheme} title="Переключить тему">
        {theme === 'dark' ? <I.Sun className="ico-sm" /> : <I.Moon className="ico-sm" />}
      </button>
      <button className="topbar-btn primary"><I.Plus className="ico-sm" />Run</button>
    </div>
  );
}

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

if (typeof window !== 'undefined') {
  Object.assign(window, { Sidebar, Topbar, FilterBar, TableHeader, EmptyState });
}
