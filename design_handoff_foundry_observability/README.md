# Handoff: Foundry · Observability UI (табличный вид)

## Обзор

Веб-интерфейс для оркестратора агентов **Foundry** — «операционная» над работой Claude Code, Codex CLI и других агентских раннеров. Показывает список задач (issue → PR), их текущую стадию, и — при раскрытии — интерактивный таймлайн стадий с потоком tool-use событий агента и композером «задать вопрос модели».

Визуальный язык: тёплый тёмный фон в духе Codex (бежевый-песочный на dark), оранжевый акцент `#D97757`, тонкие бордеры, моноширинные технические данные, плотная но дышащая сетка.

## О файлах в этом пакете

HTML/JSX в этой папке — **дизайн-референсы**, не продакшн-код для прямого включения. Задача — воссоздать эти экраны в вашем существующем окружении (React + Next.js / Vite / что угодно), используя ваши компоненты и стили. Если окружения ещё нет — выбирайте React + Vite + TypeScript.

**Как открыть пакет для просмотра:** откройте `Foundry Tasks.html` через локальный static-сервер (иначе браузер не даст `<script src>` читать соседние .jsx). Например: `cd design_handoff_foundry_observability && python3 -m http.server 8000`, затем [http://localhost:8000/Foundry Tasks.html](http://localhost:8000/Foundry%20Tasks.html).

## Фидельность

**Hi-fi.** Цвета, типографика, отступы, бордеры, shadow'ы — финальные. Иконки нарисованы SVG в `icons.jsx` и легко заменяются на Lucide / Radix Icons (формы совпадают с `lucide-react` один-к-одному, это было целью). Копирайтинг на русском — использовать как есть или адаптировать.

## Экран

### Единственный экран: «Задачи» (табличный список)

**Что делает пользователь:** сканирует список запущенных/завершённых задач, разворачивает одну, видит в реальном времени что делает агент и на какой он стадии, задаёт уточняющие вопросы модели прямо из UI.

**Layout (3-колоночный):**
- **Sidebar** (слева, фикс. 232px): брендинг + навигация + список репозиториев + мини-виджет «Сегодня» с расходом.
- **Main column** (flex 1): topbar → фильтр-бар → заголовок таблицы → строки задач.
- **Expanded panel** (inline, внутри строки): шапка с мета-данными → кликабельный stepper → детальная панель выбранной стадии.

### Компоненты экрана

#### Sidebar
- Ширина: `232px`, фон `var(--bg-1)`, правый бордер `1px solid var(--border)`.
- Логотип: квадрат `28×28`, `border-radius: 6px`, фон `var(--accent)` (#D97757), буква `F` белым, 14px bold.
- Разделы через заголовки с `letter-spacing: .1em; text-transform: uppercase; font-size: 10.5px; color: var(--fg-2)`.
- `.nav-item`: высота `30px`, padding `6px 10px`, gap `10px`, иконка 14px. Активный → левый бордер `2px solid var(--accent)` + фон `var(--bg-2)`.
- Мини-счётчик справа: моноширинный, `font-size: 11px`, `color: var(--fg-2)`.
- Виджет «Сегодня» внизу: карточка с 1px бордером, показывает сумму расходов и кол-во задач.

#### Topbar
- Высота `48px`, фон `var(--bg-1)`, нижний бордер.
- Слева — заголовок страницы с иконкой-оранжевой-inbox, затем мелкая крошка «все репозитории».
- Справа — поиск (плашка `260×28px` с иконкой и `⌘K` kbd-хинтом), toggle темы, primary-кнопка `Run`.

#### FilterBar
- Высота `42px`, горизонтальные pill-кнопки.
- `.filter-pill`: height `24px`, padding `0 10px`, `border-radius: 999px`, thin бордер. Активный вариант: фон `var(--bg-2)`, `color: var(--fg-0)`, бордер `var(--border-strong)`.
- У кнопки «Активные» — мигающая оранжевая точка `.dot-running` (6px, radial gradient).

#### Заголовок таблицы
- Grid: `22px 92px 1fr 240px 80px 80px 24px`, gap `14px`, padding `7px 20px`.
- Все заголовки `uppercase 10px 600 .1em letter-spacing color: var(--fg-2)`.

#### Строка задачи (свёрнутая)
- Grid совпадает с заголовком. Высота `~44px`, padding `10px 20px 10px 22px`.
- Клик по строке — раскрывает/сворачивает.
- Hover: фон `var(--bg-1)`.
- Активная (RUNNING) строка: слева тонкий `2px` оранжевый ribbon — `.selected-bar`.
- Колонки:
  1. Стрелка-chevron, поворот 90° при раскрытии.
  2. `<StatusChip>` — pill со статусом (RUNNING / DONE / FAILED / PENDING).
  3. Заголовок: `#412 · Текст issue`, 13px, `color: var(--fg-0)`; справа мелко репо и автор.
  4. `<StageStepper size="sm">` — 6 точек со коннекторами.
  5. Длительность (`2m 14s`, tabular-nums).
  6. Стоимость в долларах + токены мелко (tabular-nums, 10.5px color fg-2).

#### StatusChip
```
RUNNING → фон #FEF3E4 (light) / rgba(217,119,87,.14) (dark), текст #D97757, мигающая точка
DONE    → фон rgba(34,139,89,.12), текст #2E8555
FAILED  → фон rgba(220,65,65,.14), текст #DC4141
PENDING → фон var(--bg-2), текст var(--fg-2)
```
- border-radius: `4px`, padding `2px 7px`, font-size `10.5px`, letter-spacing `.04em`, text-transform `uppercase`, font-weight `600`.
- В RUNNING — `<span class="dot dot-running">` слева (radial-gradient оранж).

#### StageStepper
Горизонтальный stepper из 6 стадий: `fetch → context → agent_plan → agent_implement → test → pr`.
Три размера: `sm` (dot 6px, gap 28px), `md` (dot 10px, gap 40px), `lg` (dot 14px, gap 64px + подписи под).

**Состояния dot'а:**
- `done` → заливка `var(--success)` (#2E8555), галочка внутри
- `running` → заливка `var(--running)` (#D97757), пульсирующая (box-shadow animation 1.4s infinite)
- `failed` → заливка `var(--danger)` (#DC4141), крестик внутри
- `pending` → заливка `var(--bg-2)`, бордер `var(--border-strong)`
- `skipped` → dashed бордер

**Коннектор между dot'ами:**
- `height: 1px` (sm) / `2px` (md, lg).
- От done до done — сплошной `var(--success)`.
- От done до running — оранжевый градиент.
- От running дальше — пунктирный `var(--border-strong)`.

**Интерактивность (size="lg"):**
- Пропы: `onStageClick(stageId)`, `selectedStage`.
- Hover — scale(1.2), ring 2px `var(--accent)`.
- Выбранная стадия — постоянный ring 2px.

#### Expanded details (раскрытая панель внутри строки)

Вставляется inline под строкой с `border-top: 1px solid var(--border)`, `background: var(--bg-0)`, padding `16px 24px 18px`.

**Структура:**
1. **Meta-header** (grid `1fr auto`):
   - issue body (lead 13px, fg-1, text-wrap: pretty, max-width 720px)
   - labels (pill'ы 11px)
   - ряд мета: автор, branch, worktree, ссылка на GH issue (моно 11.5px)
   - справа — кнопки действий (Cancel / Retry / Open PR)
2. **Таймлайн стадий** (card): заголовок «ТАЙМЛАЙН СТАДИЙ» + подсказка «кликните на стадию…» → `<StageStepper size="lg" showLabels onStageClick={...} selectedStage={...}>`.
3. **Stage detail panel** (см. ниже).
4. Блок ошибки (если стадия не текущая и есть error) — баннер с фоном `var(--danger-soft)`.

#### Stage detail panel

Карточка с `border-radius: 8px`, состоит из:

**Шапка стадии** (padding `12px 18px`, нижний бордер):
- Слева: uppercase-лейбл стадии (RUNNING → оранжевый fg, DONE → зелёный, FAILED → красный), статус со спиннером/галочкой/крестом.
- Справа: `<AgentBadge>` с именем и моделью агента, затем метрики (время / $ / токены) мелко моно.
- Для RUNNING — фон шапки `var(--running-soft)`; для FAILED — `var(--danger-soft)`.

**Тело** (grid):
- Для агентских стадий (agent_plan, agent_implement): `1fr 1.4fr 1fr` → **Вход / Поток событий / Выход**.
- Для не-агентских: `1fr 1fr` → **Вход / Выход**.
- Min-height 240px.
- Каждый sub-блок — `<StageSubblock>` с заголовком (uppercase 10px) и рамкой-разделителем `border-right: 1px solid var(--border)`.

**Вход / Выход** — `<StageIO>` рисует разные типы данных:
- `kind: 'kv'` — определения ключ-значение, моно, grid `auto 1fr`.
- `kind: 'files'` — список файлов с иконкой папки.
- `kind: 'text'` — длинный текст (план, stdout).
- `kind: 'error'` — с красным лейблом и моно-текстом.
- `kind: 'pending'` — спиннер + надпись.

**Поток событий стадии** — переиспользованный `<EventStream>` (см. ниже), отфильтрованный по `stage === selectedStage`, с max-height 300px и overflow-y.

**AgentBadge:**
- Inline-flex, padding `3px 8px 3px 4px`, border-radius 999px, bg-0, border.
- Слева — круглый значок 18×18, фон `var(--accent)`, sparkline-иконка белым.
- Текст: имя агента (fg-0) + точка + модель моно 10.5px (fg-1).

**AskAgentComposer** (появляется только для агентских стадий):
- Свёрнутая строка: `padding 10px 14px`, фон `var(--bg-1)`, иконка Thinking (жёлтая) + «Уточнить у <агент> — что именно сделано и почему» + кнопка «Задать вопрос» с хинтом `/`.
- Раскрытый: textarea с placeholder, кнопки Отмена / Отправить, подсказка «⌘+Enter — отправить».

#### EventStream / EventRow

Рендерит список событий агента. Три стиля (переключаются пропом `style`):

**`telegram`** (по умолчанию):
- Каждое событие — плашка с иконкой инструмента (⚙ Tool: detail).
- Иконка инструмента: `var(--tool-color)`, 16×16.
- Формат: `<tool name>` bold → двоеточие → short detail моноширинным.
- Событие типа `thinking` — серый курсив с бледной «лампочкой».
- Событие типа `text` — обычный текст, отступ слева 22px.
- live-событие (последнее) — мигающий caret в конце.

**`terminal`**:
- Моноширинный сплошной блок.
- Каждая строка: `$>` → `<tool>` → args inline.
- Белый текст на фоне bg-0, легкая подсветка `tool` зелёным.

**`cards`**:
- Каждое событие — отдельная пилюля: иконка | tool | detail.
- Более кликабельно, но занимает больше места.

#### Цвета инструментов (TOOL_COLORS в components.jsx)

```
Read      #7FA7D9   (голубой)
Edit      #D98A5A   (терракота)
Bash      #B88AE6   (пурпур)
Grep      #E6B85A   (горчица)
Write     #7BB97B   (зелёный)
WebFetch  #5ABEBE   (бирюза)
Task      #C77DD9   (розовый)
Thinking  #8A7A5F   (приглушённый)
Final     var(--fg-0)
```

## Интерактив

### Навигация по стадиям
- Клик на stage-dot в big stepper → переключает `selectedStage` → обновляется `StageDetailPanel`.
- При раскрытии задачи: по умолчанию выбирается первая стадия в порядке приоритета `running > failed > последняя done > первая`.

### Раскрытие задач
- Клик по строке / chevron → тогглит expanded.
- В прототипе позволено расширить только одну задачу за раз. В продакшне можно оставить то же поведение или разрешить несколько.

### Live-симуляция
- Событийный поток #412 прирастает по 1 событию каждые 1800мс.
- Последнее событие маркируется `live: true` → у него показывается спиннер и мигающий caret.
- По достижении конца списка — сбрасывается к 16 (для демо).

### Анимации
- `.dot-running` — пульсация через `@keyframes pulse` (1.4s infinite, box-shadow 0 → 6px rgba accent).
- Раскрытие expanded — не анимируется, instant (сознательно, плотность > мягкость).
- Chevron — `transform: rotate(90deg)` с `transition: transform .18s cubic-bezier(.2,.7,.3,1)`.
- Spinner — `border-top-color: transparent` вращается 0.8s linear infinite.

## Состояние

### Ключевой стейт (в `main.jsx`)
```ts
theme: 'dark' | 'light'          // тема, пишется в data-theme на <html>
filter: 'all' | 'RUNNING' | 'DONE' | 'FAILED' | 'PENDING'
expandedId: string | null        // id раскрытой задачи
selectedStage: StageId           // внутри TaskDetails, см. task-row.jsx
```

### Model задачи (см. `data.js` → `TASKS`)
```ts
type Task = {
  id: string;                              // 'tsk_7f2a9c'
  status: 'RUNNING' | 'DONE' | 'FAILED' | 'PENDING';
  repo: string;                            // 'acme/foundry-web'
  branch?: string;
  worktree?: string;
  issue_number: number;
  issue_title: string;
  issue_body?: string;
  issue_author: string;
  issue_labels: string[];
  started_at: ISOString;
  duration_sec: number;
  total_cost_usd: number;
  tokens_total: number;
  pr_url?: string;
  pr_number?: number;
  error?: { stage: StageId; message: string; trace: string[] };
  stages: Record<StageId, Stage>;
};

type StageId = 'fetch' | 'context' | 'agent_plan' | 'agent_implement' | 'test' | 'pr';

type Stage = {
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped';
  duration?: number;          // секунды
  cost?: number;              // USD
  tokens_in?: number;
  tokens_out?: number;
  agent?: { name: string; model: string; provider: string };
  input?: IOData;
  output?: IOData;
};

type IOData =
  | { kind: 'kv'; items: [string, string][] }
  | { kind: 'files'; label: string; items: string[] }
  | { kind: 'text'; label?: string; text: string }
  | { kind: 'error'; label: string; text: string }
  | { kind: 'pending'; label: string };
```

### Event
```ts
type Event = {
  id: string;
  stage: StageId;                        // к какой стадии привязано
  kind: 'tool' | 'thinking' | 'text';
  tool?: 'Read' | 'Edit' | 'Bash' | 'Grep' | 'Write' | 'WebFetch' | 'Task';
  detail?: string;                       // "src/foo.py:42-58" для Read
  args?: string;                         // для bash — команда
  text?: string;                         // для thinking / text
  live?: boolean;                        // добавляется runtime для последнего
  ts: number;                            // ms от старта
};
```

Данные для задачи #412 лежат в `EVENTS_412` в `data.js` — 42 события по всем стадиям.

### Фетчинг (в реальной реализации)
Рекомендуем WebSocket / SSE для live-потока событий + REST для списка задач и полных данных по одной задаче. В демо всё статично + setInterval для симуляции live.

## Design tokens

Все токены — CSS custom properties в `styles.css`. Переключаются через `data-theme` на `<html>`.

### Dark theme (default — как Codex)
```
--bg-0: #1E1C17         // основной фон
--bg-1: #26241E         // поверхности, сайдбар, topbar
--bg-2: #332E24         // hover, активные состояния
--fg-0: #EAE3D2         // primary text
--fg-1: #C6BCA5         // secondary
--fg-2: #8C8371         // tertiary, мелкие подписи
--fg-3: #6C6455         // самые тихие, ghost
--border: #3B362C
--border-soft: #2E2A22
--border-strong: #4A4537
--accent: #D97757       // оранжевый Claude/Codex
--accent-soft: rgba(217,119,87,.14)
--success: #2E8555
--success-soft: rgba(46,133,85,.14)
--running: #D97757
--running-soft: rgba(217,119,87,.14)
--danger: #DC4141
--danger-soft: rgba(220,65,65,.14)
--highlight: #E6B85A    // жёлтый (thinking)
```

### Light theme
```
--bg-0: #F9F5EC
--bg-1: #FEFBF2
--bg-2: #F1EADB
--fg-0: #29261B
--fg-1: #4D4838
--fg-2: #7C745E
--fg-3: #A29884
--border: #E4DCC6
--border-soft: #EEE6D2
--border-strong: #C9BEA0
--accent: #C65A2F       // чуть темнее на свету
--success: #2E8555
--running: #C65A2F
--danger: #B83535
--highlight: #9C7A1F
```

### Радиусы
```
--r-sm: 4px     // chip, badge
--r-md: 6px     // card, button, input
--r-lg: 10px    // большие карточки
```

### Тени
```
--shadow-1: 0 1px 0 rgba(0,0,0,.04), 0 2px 6px rgba(0,0,0,.08);
--shadow-2: 0 4px 20px rgba(0,0,0,.18);   // dark
          : 0 4px 20px rgba(40,30,15,.06); // light
```

### Типографика
- Main sans: `-apple-system, "SF Pro Text", "Inter", system-ui, sans-serif`.
- Mono (`.mono`): `"SF Mono", "JetBrains Mono", "IBM Plex Mono", Menlo, Consolas, monospace`.
- **На продакшне рекомендуем**: `Inter` для UI, `JetBrains Mono` для моно. Claude/Codex используют `"Söhne"` + `"Söhne Mono"` — это платные; Inter/JetBrains — достойные open-source эквиваленты.
- Tabular-nums (`.tabular`): `font-variant-numeric: tabular-nums`. Для всех цифровых значений (длительность, токены, $).

### Spacing / sizing
- Base unit: `4px`.
- Высоты: строка задачи `44px`, topbar `48px`, filter-bar `42px`, nav-item `30px`.
- Paddings: `16-20px` для контейнеров, `10-14px` для строк, `6-10px` для inline-элементов.

## Ассеты

- **Иконки** все нарисованы inline SVG в `icons.jsx`. Формы совпадают с `lucide-react` — можно заменить на него один-к-одному. Единственное своё — `Spark` и `Final` (чекмарка).
- **Логотип F**: просто буква в оранжевом квадрате — в продакшне замените на настоящий лого Foundry.

## Файлы в пакете

- `Foundry Tasks.html` — точка входа
- `styles.css` — все стили и design tokens
- `data.js` — моковые задачи и события (`TASKS`, `EVENTS_412`, `STAGES`)
- `icons.jsx` — SVG-иконки (экспорт `I`)
- `components.jsx` — `StatusChip`, `StageStepper`, `StageDots`, `EventStream` (три стиля), `formatDuration`, `formatCost`, `RepoLabel`, `CostCell`, `TOOL_COLORS`
- `task-row.jsx` — `TaskRowLinear`, `TaskCard`, `TaskRowCompact`, `TaskDetails` (со всей раскрытой панелью: `StageDetailPanel`, `StageSubblock`, `StageIO`, `AgentBadge`, `AskAgentComposer`)
- `shell.jsx` — `Sidebar`, `Topbar`, `FilterBar`, `TableHeader`, `EmptyState`
- `main.jsx` — `App` + `useLiveEvents`

## Следующие шаги для реализации

1. Скопировать токены из `styles.css` в вашу систему стилей (или оставить как CSS vars).
2. Заменить SVG из `icons.jsx` на `lucide-react` — формы уже совпадают.
3. Перевести `data.js` в TypeScript-типы (типы выше).
4. Разобрать `task-row.jsx` на TSX-компоненты (`TaskRowLinear`, `TaskDetails`, `StageDetailPanel`, `StageIO`, `AgentBadge`, `AskAgentComposer`).
5. Подключить реальные API: `GET /tasks`, `GET /tasks/:id`, WebSocket на `/tasks/:id/events`.
6. На старте — табличный layout единственным. Карточный/компактный хранятся в главном прототипе (`../Foundry Observability.html`) как резерв.
