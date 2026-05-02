// main.jsx — root приложения: Shell + таблица задач + live-симуляция.
// Без design_canvas и tweaks. Один экран, табличный вид.

function useLiveEvents(enabled, speed) {
  const FULL = EVENTS_412;
  const [count, setCount] = React.useState(16);

  React.useEffect(() => {
    if (!enabled) return;
    const interval = 1800 / speed;
    const t = setInterval(() => {
      setCount(c => (c >= FULL.length ? 16 : c + 1));
    }, interval);
    return () => clearInterval(t);
  }, [enabled, speed]);

  const visible = FULL.slice(0, count).map((e, i, arr) => {
    if (i === arr.length - 1 && enabled && e.kind === 'tool') return { ...e, live: true };
    return e;
  });
  return visible;
}

function App() {
  const [theme, setTheme] = React.useState('dark');
  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const [filter, setFilter] = React.useState('all');
  const [expandedId, setExpandedId] = React.useState('tsk_7f2a9c');
  const events = useLiveEvents(true, 1.0);

  const counts = React.useMemo(() => ({
    total: TASKS.length,
    running: TASKS.filter(t => t.status === 'RUNNING').length,
    done: TASKS.filter(t => t.status === 'DONE').length,
    failed: TASKS.filter(t => t.status === 'FAILED').length,
    pending: TASKS.filter(t => t.status === 'PENDING').length,
  }), []);
  const filtered = filter === 'all' ? TASKS : TASKS.filter(t => t.status === filter);

  return (
    <div className="app-shell">
      <Sidebar counts={counts} />
      <div className="main">
        <Topbar theme={theme} onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')} />
        <FilterBar filter={filter} setFilter={setFilter} counts={counts} />
        <TableHeader />
        {filtered.map(t => (
          <TaskRowLinear
            key={t.id}
            task={t}
            expanded={expandedId === t.id}
            onToggle={() => setExpandedId(expandedId === t.id ? null : t.id)}
            eventStyle="telegram"
            showThinking={true}
            events={t.id === 'tsk_7f2a9c' ? events : []}
          />
        ))}
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
