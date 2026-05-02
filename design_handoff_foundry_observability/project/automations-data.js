// automations-data.js — данные для Automations Factory UI
// Triggers (long-running listeners), Automations (декл. правила),
// Runs (запуски), Tree-events (вложенное дерево вызовов).

// ─── Triggers ──────────────────────────────────────────────────
const TRIGGERS = [
  { id: 'gh_issues',    kind: 'github',  name: 'GitHub Issues · acme/foundry-web', health: 'ok',     last_seen: '2 мин',   detail: 'label:foundry-run' },
  { id: 'gh_pr',        kind: 'github',  name: 'GitHub PRs · acme/*',              health: 'ok',     last_seen: '14 мин',  detail: 'opened, ready_for_review' },
  { id: 'discord_main', kind: 'discord', name: 'Discord · #product',               health: 'ok',     last_seen: '47 сек',  detail: 'mentions @foundry' },
  { id: 'discord_eng',  kind: 'discord', name: 'Discord · #engineering',           health: 'ok',     last_seen: '3 мин',   detail: 'mentions @foundry' },
  { id: 'cron_digest',  kind: 'cron',    name: 'Cron · daily 09:00',               health: 'waiting',last_seen: '14 ч',    detail: '0 9 * * *' },
  { id: 'wh_linear',    kind: 'webhook', name: 'Webhook · Linear',                 health: 'down',   last_seen: '2 ч',     detail: '401 unauthorized — нужен новый token' },
];

// ─── Automations ───────────────────────────────────────────────
const AUTOMATIONS = [
  {
    id: 'dev_task',
    name: 'dev_task',
    description: 'Issue → branch → план → impl → тесты → PR (legacy pipeline)',
    color: '#D97757',
    icon: 'Branch',
    triggers: ['gh_issues'],
    agent: { name: 'claude code', model: 'claude-sonnet-4.5' },
    skills: ['open_worktree', 'plan', 'implement', 'run_tests', 'create_pr', 'mark_milestone'],
    expected_milestones: ['plan', 'implement', 'verify', 'pr'],
    counts: { running: 1, today: 5, week: 23, failed_today: 1 },
  },
  {
    id: 'pr_reviewer',
    name: 'pr_reviewer',
    description: 'Реагирует на новые PR, оставляет инлайн-комментарии и summary',
    color: '#7BB97B',
    icon: 'GitHub',
    triggers: ['gh_pr'],
    agent: { name: 'claude code', model: 'claude-sonnet-4.5' },
    skills: ['fetch_diff', 'review_inline', 'post_summary', 'react'],
    expected_milestones: null,
    counts: { running: 2, today: 8, week: 41, failed_today: 0 },
  },
  {
    id: 'intent_collection',
    name: 'intent_collection',
    description: 'Слушает Discord, собирает контекст обсуждения как «намерение»',
    color: '#7FA7D9',
    icon: 'Discord',
    triggers: ['discord_main', 'discord_eng'],
    agent: { name: 'claude code', model: 'claude-haiku-4.5' },
    skills: ['reply_discord', 'react', 'compact', 'mark_intent'],
    expected_milestones: null,
    counts: { running: 1, today: 12, week: 68, failed_today: 0 },
  },
  {
    id: 'intent_to_task',
    name: 'intent_to_task',
    description: 'Превращает обсуждение из intent_collection в GitHub issue',
    color: '#C77DD9',
    icon: 'Spark',
    triggers: ['discord_main'],
    agent: { name: 'claude code', model: 'claude-sonnet-4.5' },
    skills: ['open_issue', 'reply_discord', 'mark_milestone'],
    expected_milestones: ['draft', 'review', 'submitted'],
    counts: { running: 0, today: 2, week: 7, failed_today: 0 },
  },
  {
    id: 'daily_digest',
    name: 'daily_digest',
    description: 'Cron-дайджест активности команды в Discord',
    color: '#E6B85A',
    icon: 'Clock',
    triggers: ['cron_digest'],
    agent: { name: 'claude code', model: 'claude-haiku-4.5' },
    skills: ['list_runs', 'list_prs', 'post_discord'],
    expected_milestones: null,
    counts: { running: 0, today: 0, week: 6, failed_today: 0 },
  },
];

// ─── Runs (для pr_reviewer и dev_task показываем подробно) ─────
const RUNS = [
  // dev_task
  {
    id: 'run_e84a',
    automation: 'dev_task',
    status: 'RUNNING',
    session_id: 'sess_412_devtask',
    session_seq: 1,
    started_at: '14:38:04',
    duration_sec: 134,
    cost_usd: 0.42,
    sub_calls: 2,
    trigger: { kind: 'github', source: 'github · acme/foundry-web', event_id: 'issue #412', author: 'mikhail',
               text: 'Add real-time agent action visibility to task rows — currently we only see start/stop, but not what the agent is actually doing.' },
    expected_milestones: ['plan', 'implement', 'verify', 'pr'],
    milestones_done: ['plan'],
    milestones_running: 'implement',
  },
  {
    id: 'run_d12b',
    automation: 'dev_task',
    status: 'DONE',
    session_id: 'sess_408_devtask',
    session_seq: 1,
    started_at: '13:12:00',
    duration_sec: 287,
    cost_usd: 0.91,
    sub_calls: 3,
    trigger: { kind: 'github', source: 'github · acme/foundry-web', event_id: 'issue #408', author: 'anya',
               text: 'Persist task list across page reloads using localStorage' },
    expected_milestones: ['plan', 'implement', 'verify', 'pr'],
    milestones_done: ['plan', 'implement', 'verify', 'pr'],
  },
  {
    id: 'run_a93c',
    automation: 'dev_task',
    status: 'FAILED',
    failure_kind: 'deterministic',
    failure_msg: '3 теста упали в tests/cli/test_watch.py — assertion на формат events',
    session_id: 'sess_396_devtask',
    session_seq: 2,
    started_at: '11:02:14',
    duration_sec: 412,
    cost_usd: 1.23,
    sub_calls: 2,
    trigger: { kind: 'github', source: 'github · acme/foundry-cli', event_id: 'issue #396', author: 'kirill',
               text: 'Allow `foundry run --watch` to attach to running session' },
  },
  {
    id: 'run_a93b',
    automation: 'dev_task',
    status: 'DONE',
    session_id: 'sess_396_devtask',
    session_seq: 1,           // first attempt, same session as above
    started_at: '10:14:22',
    duration_sec: 198,
    cost_usd: 0.51,
    sub_calls: 1,
    trigger: { kind: 'github', source: 'github · acme/foundry-cli', event_id: 'issue #396', author: 'kirill',
               text: 'Allow `foundry run --watch` to attach to running session' },
    expected_milestones: ['plan', 'implement', 'verify', 'pr'],
    milestones_done: ['plan', 'implement', 'verify', 'pr'],
    note: 'preempted — kirill переоткрыл issue с правками, см. run выше',
  },
  // pr_reviewer
  {
    id: 'run_b71f',
    automation: 'pr_reviewer',
    status: 'RUNNING',
    session_id: 'sess_pr847',
    session_seq: 1,
    started_at: '14:51:08',
    duration_sec: 22,
    cost_usd: 0.08,
    sub_calls: 0,
    trigger: { kind: 'github', source: 'github · acme/foundry-web', event_id: 'PR #847 opened', author: 'anya',
               text: 'feat(events): real-time event streaming via SSE' },
  },
  {
    id: 'run_b612',
    automation: 'pr_reviewer',
    status: 'DONE',
    session_id: 'sess_pr844',
    session_seq: 1,
    started_at: '13:40:02',
    duration_sec: 71,
    cost_usd: 0.18,
    sub_calls: 0,
    trigger: { kind: 'github', source: 'github · acme/foundry-cli', event_id: 'PR #844 opened', author: 'kirill',
               text: 'fix: handle empty events array in run --watch' },
  },
  // intent_collection
  {
    id: 'run_c401',
    automation: 'intent_collection',
    status: 'RUNNING',
    session_id: 'sess_disc_4821',
    session_seq: 4,           // continues session — 4th message in same thread
    started_at: '14:55:17',
    duration_sec: 8,
    cost_usd: 0.02,
    sub_calls: 0,
    trigger: { kind: 'discord', source: 'discord · #product', event_id: 'msg 4821', author: 'mikhail',
               text: 'Кстати, мы могли бы показывать стоимость стадий не только итоговую, но и разбивку по моделям?' },
  },
  // intent_to_task
  {
    id: 'run_d802',
    automation: 'intent_to_task',
    status: 'WAITING_HUMAN',
    session_id: 'sess_disc_4798',
    session_seq: 1,
    started_at: '14:22:00',
    duration_sec: 64,
    cost_usd: 0.14,
    sub_calls: 1,
    trigger: { kind: 'discord', source: 'discord · #product', event_id: 'msg 4798', author: 'anya',
               text: 'Нужен экран настроек для триггеров — чтобы не лазить в YAML каждый раз' },
    waiting_reason: 'Подготовлен черновик issue, агент ждёт апрува автора и тимлида перед открытием PR.',
  },
];

// ─── Tree-events для run_e84a (dev_task на issue #412) ─────────
// kind: 'text' | 'thinking' | 'tool' | 'skill' | 'subagent' | 'final' | 'mark'
// 'mark' — bright divider от skill mark_milestone, не пин в шапке.
const TREE_e84a = [
  { id: 'm1',  kind: 'mark',      label: 'plan' },
  { id: 't2',  kind: 'thinking',  text: 'Issue про live-видимость действий агента в task rows. Сначала соберу контекст, потом скажу sub-агенту планировать.', ts: '14:38:06' },
  { id: 't3',  kind: 'skill',     skill: 'open_worktree', detail: '.wt/412-real-time-visibility', ts: '14:38:08' },
  { id: 't4',  kind: 'tool',      tool: 'Read',  detail: 'src/api/main.py:1-120', ts: '14:38:10' },
  { id: 't5',  kind: 'tool',      tool: 'Grep',  detail: 'pattern: TaskRow|EventStream', files: 7, ts: '14:38:14' },
  { id: 't7',  kind: 'subagent',  agent: 'plan',
               summary: 'Готов план: in-memory EventBus → asyncio.subprocess → SSE-эндпоинт → React-хук. 4 фазы, ≈2 часа.',
               cost_usd: 0.04, duration_sec: 18,
               children: [
                 { id: 's1', kind: 'thinking', text: 'Нужно собрать контекст вокруг event-flow и UI-компонента TaskRow.' },
                 { id: 's2', kind: 'tool', tool: 'Grep', detail: 'pattern: subprocess.run', files: 4 },
                 { id: 's3', kind: 'tool', tool: 'Read', detail: 'web/src/components/TaskRow.tsx' },
                 { id: 's4', kind: 'tool', tool: 'Read', detail: 'src/foundry/db/tasks.py' },
                 { id: 's5', kind: 'final', text: '14 файлов · 3840 LoC. План: EventBus → asyncio → SSE → React-hook.' },
               ] },
  { id: 't8',  kind: 'text',      text: 'План одобряю — главная развилка между in-memory EventBus и Redis pub-sub. Беру in-memory как proof-of-concept, на Redis перейдём если будет multi-process.', ts: '14:38:42' },
  { id: 'm2',  kind: 'mark',      label: 'implement' },
  { id: 't10', kind: 'thinking',  text: 'Передаю реализацию sub-agent\'у. Сначала бэк, потом фронт.', ts: '14:38:52' },
  { id: 't11', kind: 'tool',      tool: 'Write', detail: 'src/foundry/events/bus.py (+82 строки)', ts: '14:38:55' },
  { id: 't12', kind: 'tool',      tool: 'Bash',  detail: 'pytest tests/foundry/events/ -x · ✓ 4 passed', ts: '14:39:14' },
  { id: 't14', kind: 'subagent',  agent: 'implement',
               summary: 'Готов /api/tasks/:id/events на StreamingResponse + React-хук. 7 файлов, +298 строк.',
               cost_usd: 0.11, duration_sec: 42,
               children: [
                 { id: 'u1', kind: 'thinking', text: 'SSE через FastAPI StreamingResponse + EventBus.subscribe(task_id).' },
                 { id: 'u2', kind: 'tool', tool: 'Write', detail: 'src/api/routes/events.py' },
                 { id: 'u3', kind: 'tool', tool: 'Edit',  detail: 'src/api/main.py — register router' },
                 { id: 'u4', kind: 'subagent', agent: 'react_hook_writer',
                   summary: 'Хук useEventStream(taskId) с EventSource и автоматическим reconnect.',
                   cost_usd: 0.03, duration_sec: 11,
                   children: [
                     { id: 'v1', kind: 'tool', tool: 'Write', detail: 'web/src/hooks/useEventStream.ts' },
                     { id: 'v2', kind: 'final', text: 'хук готов, экспортирован' },
                   ] },
                 { id: 'u5', kind: 'tool', tool: 'Edit', detail: 'web/src/components/TaskRow.tsx — встраиваю EventStream' },
                 { id: 'u6', kind: 'final', text: 'Бэк + фронт собраны, локально работает. Жду verify.' },
               ] },
  { id: 't15', kind: 'thinking',  text: 'Хорошо. Запускаю sub-agent verify — пусть прогонит тесты и smoke вручную.', ts: '14:40:02' },
  { id: 't16', kind: 'tool',      tool: 'Bash',  detail: 'cd .wt/412-real-time-visibility && pytest -x', live: true, ts: '14:40:04' },
];

// ─── Tree для run_b71f (pr_reviewer · быстрый, без вложенностей) ─
const TREE_b71f = [
  { id: 'r1', kind: 'skill',    skill: 'fetch_diff', detail: 'PR #847 · 4 files · +138 -22', ts: '14:51:08' },
  { id: 'r2', kind: 'thinking', text: 'Смотрю реализацию SSE — нужно проверить отписку и cleanup.', ts: '14:51:11' },
  { id: 'r3', kind: 'tool',     tool: 'Read', detail: 'src/api/routes/events.py', ts: '14:51:14' },
  { id: 'r4', kind: 'tool',     tool: 'Read', detail: 'web/src/hooks/useEventStream.ts', ts: '14:51:18' },
  { id: 'r5', kind: 'thinking', text: 'cleanup в useEffect есть, но при unmount EventSource не закрывается явно — может течь.', ts: '14:51:22', live: true },
];

// ─── Tree для run_d802 (intent_to_task · ждём human review) ─────
const TREE_d802 = [
  { id: 'i2', kind: 'thinking',  text: 'Обсуждение про экран настроек триггеров. Есть запрос (anya), есть согласие (kirill).', ts: '14:22:03' },
  { id: 'i3', kind: 'subagent',  agent: 'intent_summarizer',
               summary: 'Контекст: «Settings screen for triggers — заменить YAML-редактирование на UI».',
               cost_usd: 0.02, duration_sec: 6,
               children: [
                 { id: 'j1', kind: 'tool', tool: 'Read', detail: 'discord history msg 4790-4798' },
                 { id: 'j2', kind: 'final', text: 'Тема ясна: UI-настройка триггеров.' },
               ] },
  { id: 'i5', kind: 'text',      text: '**Черновик issue:**\n\n## Settings screen for triggers\n\nReplace YAML editing of `triggers.yaml` with a settings UI.\n\n### Acceptance\n- [ ] List active triggers\n- [ ] Edit trigger fields\n- [ ] Test connection button', ts: '14:22:52' },
  { id: 'i6', kind: 'skill',     skill: 'reply_discord', detail: 'msg 4798 — "Подготовил черновик, апрувите?"', ts: '14:22:56' },
  { id: 'i7', kind: 'text',      text: '⏳ Жду подтверждения от mikhail/anya перед открытием issue', ts: '14:23:04', live: true },
];

const RUN_TREES = {
  run_e84a: TREE_e84a,
  run_b71f: TREE_b71f,
  run_d802: TREE_d802,
};

if (typeof window !== 'undefined') {
  Object.assign(window, { TRIGGERS, AUTOMATIONS, RUNS, RUN_TREES });
}
