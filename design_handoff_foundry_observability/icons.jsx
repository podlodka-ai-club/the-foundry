// Icons.jsx — компактный набор monochrome SVG иконок (Lucide-style)
// Все иконки: stroke, 14×14 по умолчанию, currentColor.

const I = {
  // Tool icons
  Read: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M4 4h10l4 4v12H4z"/><path d="M14 4v4h4"/></svg>,
  Edit: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M4 20h4L18 10l-4-4L4 16z"/><path d="M13 7l4 4"/></svg>,
  Write: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M5 4h14v16H5z"/><path d="M9 9h6M9 13h6M9 17h4"/></svg>,
  Bash: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M5 8l4 4-4 4"/><path d="M12 16h7"/></svg>,
  Grep: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>,
  Glob: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><rect x="4" y="4" width="6" height="6"/><rect x="14" y="4" width="6" height="6"/><rect x="4" y="14" width="6" height="6"/><rect x="14" y="14" width="6" height="6"/></svg>,
  WebFetch: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18"/></svg>,
  Task: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M4 6h16M4 12h10M4 18h16"/></svg>,
  Thinking: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M12 3a6 6 0 0 0-4 10.5V17h8v-3.5A6 6 0 0 0 12 3z"/><path d="M10 20h4"/></svg>,
  Final: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M5 13l4 4L19 7"/></svg>,

  // Status
  Check: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M5 13l4 4L19 7"/></svg>,
  X:     (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M6 6l12 12M6 18L18 6"/></svg>,
  Dot:   (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><circle cx="12" cy="12" r="3"/></svg>,
  Clock: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>,
  Play:  (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M7 5v14l11-7z"/></svg>,
  Pause: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M8 5v14M16 5v14"/></svg>,

  // UI chrome
  Search:   (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>,
  Filter:   (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M4 5h16l-6 8v6l-4-2v-4z"/></svg>,
  Sort:     (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M7 4v16M3 8l4-4 4 4M17 20V4M13 16l4 4 4-4"/></svg>,
  Chevron:  (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M9 6l6 6-6 6"/></svg>,
  ChevDown: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M6 9l6 6 6-6"/></svg>,
  Plus:     (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M12 5v14M5 12h14"/></svg>,
  External: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M14 4h6v6"/><path d="M20 4L10 14"/><path d="M20 14v6H4V4h6"/></svg>,
  GitHub:   (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.8c-2.8.6-3.4-1.3-3.4-1.3-.5-1.1-1.1-1.4-1.1-1.4-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8 0-.6.3-1.1.6-1.4-2.2-.2-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.5-1.3.1-2.7 0 0 .8-.3 2.7 1a9.4 9.4 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .6 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.4 4.7-4.6 5 .4.3.7.9.7 1.8v2.7c0 .3.2.6.7.5A10 10 0 0 0 12 2z"/></svg>,
  Branch:   (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="7" r="2"/><path d="M6 7v10M6 13c0-4 4-4 4-4h6"/></svg>,
  Retry:    (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>,
  Cancel:   (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><rect x="6" y="6" width="12" height="12" rx="1"/></svg>,
  Sun:      (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/></svg>,
  Moon:     (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10z"/></svg>,
  Home:     (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M3 11l9-7 9 7v9H3z"/></svg>,
  List:     (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M4 6h16M4 12h16M4 18h16"/></svg>,
  Package:  (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M3 7l9-4 9 4-9 4zM3 7v10l9 4M21 7v10l-9 4"/></svg>,
  Settings: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2.1-1.2L14 3h-4l-.4 2.6A7 7 0 0 0 7.5 6.8l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1c.6.5 1.3.9 2.1 1.2L10 21h4l.4-2.6a7 7 0 0 0 2.1-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z"/></svg>,
  Activity: (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M3 12h4l3-8 4 16 3-8h4"/></svg>,
  Inbox:    (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M3 13l4-9h10l4 9v6H3z"/><path d="M3 13h5l1 3h6l1-3h5"/></svg>,
  Dollar:   (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M12 3v18M16 7H9.5a2.5 2.5 0 0 0 0 5h5a2.5 2.5 0 0 1 0 5H7"/></svg>,
  Folder:   (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>,
  User:     (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>,
  Hash:     (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M5 9h14M5 15h14M10 3L8 21M16 3l-2 18"/></svg>,
  Layout:   (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>,
  Spark:    (p) => <svg {...p} viewBox="0 0 24 24" className={`ico ${p.className||''}`}><path d="M12 2v4M12 18v4M5 5l2.5 2.5M16.5 16.5L19 19M2 12h4M18 12h4M5 19l2.5-2.5M16.5 7.5L19 5"/></svg>,
};

// Tool dispatcher — выбирает иконку по названию инструмента
function ToolIcon({ tool, ...rest }) {
  const key = tool === 'Read' ? 'Read'
    : tool === 'Edit' ? 'Edit'
    : tool === 'Write' ? 'Write'
    : tool === 'Bash' ? 'Bash'
    : tool === 'Grep' ? 'Grep'
    : tool === 'Glob' ? 'Glob'
    : tool === 'WebFetch' ? 'WebFetch'
    : tool === 'Task' ? 'Task'
    : 'Dot';
  const Cmp = I[key];
  return <Cmp {...rest} />;
}

if (typeof window !== 'undefined') Object.assign(window, { I, ToolIcon });
