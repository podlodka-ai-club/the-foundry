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

export interface SessionGroup<T> {
  session_id: string;
  runs: T[];
  latest: T;
}

/**
 * Group runs by `session_id` so the session itself is the unit shown in
 * lists. Inside each group runs go newest-first; groups are ordered by
 * the latest run's id (newest first).
 */
export function groupBySession<T extends { id: number; session_id: string; session_seq: number }>(
  runs: T[],
): SessionGroup<T>[] {
  const map = new Map<string, T[]>();
  for (const r of runs) {
    const arr = map.get(r.session_id);
    if (arr) arr.push(r);
    else map.set(r.session_id, [r]);
  }
  const out: SessionGroup<T>[] = [];
  for (const [sid, list] of map) {
    list.sort((a, b) => b.session_seq - a.session_seq || b.id - a.id);
    out.push({ session_id: sid, runs: list, latest: list[0] });
  }
  out.sort((a, b) => b.latest.id - a.latest.id);
  return out;
}

export function pluralRu(n: number, forms: [string, string, string]): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1];
  return forms[2];
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
