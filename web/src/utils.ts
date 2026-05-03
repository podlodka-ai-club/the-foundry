// Formatting helpers.

export function formatDurationMs(ms: number | null | undefined): string {
  if (!ms || ms <= 0) return "—";
  const sec = ms / 1000;
  if (sec < 60) return `${Math.round(sec)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

export function formatCost(usd: number | null | undefined): string {
  if (!usd) return "$0.00";
  return `$${usd.toFixed(2)}`;
}

export function formatTokens(total: number): string {
  if (!total) return "0";
  if (total < 1000) return `${total}`;
  return `${(total / 1000).toFixed(1)}k`;
}
