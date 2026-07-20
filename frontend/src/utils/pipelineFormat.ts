// Duration/timestamp formatting for pipeline rows. Leaf module (no
// store/api/i18n imports) extracted from PipelineOperationsConsolePage
// while paying down its component-size overage.

export function fmtDuration(a: string | null, b: string | null): string {
  if (!a) return '—';
  const start = new Date(a).getTime();
  const end = b ? new Date(b).getTime() : Date.now();
  const ms = Math.max(0, end - start);
  // Sub-second jobs render "<1s" instead of "0s" — common for the
  // trailing aggregation after 4A.3 scoped the write set down to just
  // the affected modules.  "0s" read as "didn't run"; "<1s" says
  // "ran, was just fast".
  if (ms < 1000) return ms === 0 && !b ? '—' : '<1s';
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m${String(s % 60).padStart(2, '0')}s`;
  return `${Math.floor(m / 60)}h${String(m % 60).padStart(2, '0')}m`;
}

/**
 * Queue wait (created → started), or null when it isn't worth showing
 * (missing timestamps, or under 2s — chain/poller latency noise).
 */
export function fmtQueued(
  created: string | null,
  started: string | null,
): string | null {
  if (!created || !started) return null;
  const ms = new Date(started).getTime() - new Date(created).getTime();
  if (ms < 2000) return null;
  return fmtDuration(created, started);
}

export function fmtWhen(s: string | null): string {
  if (!s) return '—';
  return new Date(s).toLocaleString();
}
