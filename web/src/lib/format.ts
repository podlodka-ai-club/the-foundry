export function fmtDuration(sec: number | null): string {
  if (sec === null || sec === undefined) return '—';
  if (sec < 60) return `${sec.toFixed(1)}s`;
  if (sec < 3600) {
    const m = Math.floor(sec / 60);
    const r = Math.floor(sec % 60);
    return r ? `${m}m ${r}s` : `${m}m`;
  }
  return `${(sec / 3600).toFixed(1)}h`;
}

export function fmtCost(usd: number | null): string {
  if (usd === null || usd === undefined) return '—';
  if (usd === 0) return '$0.00';
  if (usd < 0.01) return '<$0.01';
  return `$${usd.toFixed(2)}`;
}

export function fmtRelativeTime(iso: string | null): string {
  if (!iso) return 'never';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return 'never';
  const ago = (Date.now() - t) / 1000;
  if (ago < 60) return 'just now';
  if (ago < 3600) return `${Math.floor(ago / 60)}m ago`;
  if (ago < 86400) return `${Math.floor(ago / 3600)}h ago`;
  return `${Math.floor(ago / 86400)}d ago`;
}
