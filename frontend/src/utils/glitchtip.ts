// Minimal GlitchTip/Sentry-compatible error reporter (~1–2 KB).
//
// We deliberately avoid @sentry/vue: this app only needs crash visibility, not
// tracing/replay/feedback. The client speaks the Sentry "envelope" ingest
// protocol, which GlitchTip accepts. It is a module-level singleton so any
// module (api/http.ts, the router, the global handlers in boot/sentry.ts) can
// report via captureError() without prop-drilling — the role @sentry/vue's
// global captureMessage used to play. Without a DSN, init is a no-op, so dev
// and CI stay silent.

export interface CaptureContext {
  // Sentry "mechanism": how the error surfaced (onerror, vue, vue-router, …).
  // Drives grouping and the handled/unhandled badge in the GlitchTip UI.
  mechanism?: string;
  handled?: boolean;
  level?: 'error' | 'warning' | 'info';
  extra?: Record<string, unknown>;
}

export interface GlitchTipOptions {
  dsn: string;
  release?: string;
  environment?: string;
  // Messages matching any entry are dropped before sending (browser noise,
  // user-driven aborts). Mirrors @sentry/vue's `ignoreErrors`.
  ignoreErrors?: (string | RegExp)[];
  maxBreadcrumbs?: number;
}

interface Breadcrumb {
  timestamp: number;
  message: string;
  category: string;
}

interface StackFrame {
  function: string;
  filename: string;
  lineno: number;
  colno: number;
  in_app: boolean;
}

const OFFLINE_KEY = 'gtq';

// Normalize anything thrown (Error, string, ErrorEvent.message, rejection
// reason) into an Error so we always have name/message/stack to report.
function toError(raw: unknown): Error {
  if (raw instanceof Error) return raw;
  if (typeof raw === 'string') return new Error(raw);
  const message = (raw as { message?: unknown } | null)?.message;
  return new Error(message != null ? String(message) : 'Unknown error');
}

// Best-effort parse of an Error.stack into Sentry frames. Handles Chrome
// ("at fn (url:line:col)") and Firefox/Safari ("fn@url:line:col"). The leading
// "Error: message" line and any unparseable line are dropped. Frames are
// reversed because Sentry renders them oldest-call-first.
function parseStack(stack?: string): { frames: StackFrame[] } | undefined {
  if (!stack) return undefined;
  const frames = stack
    .split('\n')
    .map((raw): StackFrame | null => {
      const m = raw
        .trim()
        .match(/^(?:at\s+)?(?:(.+?)\s*[(@])?\s*(.+?):(\d+):(\d+)\)?$/);
      if (!m) return null;
      return {
        function: m[1] || '<anonymous>',
        filename: m[2],
        lineno: Number(m[3]),
        colno: Number(m[4]),
        in_app: true,
      };
    })
    .filter((f): f is StackFrame => f !== null)
    .reverse();
  return frames.length ? { frames } : undefined;
}

function matchesAny(message: string, patterns: (string | RegExp)[]): boolean {
  return patterns.some((p) =>
    typeof p === 'string' ? message.includes(p) : p.test(message),
  );
}

interface Client {
  capture: (raw: unknown, ctx?: CaptureContext) => void;
  breadcrumb: (message: string, category?: string) => void;
}

let client: Client | null = null;

export function initGlitchTip(opts: GlitchTipOptions): void {
  const { dsn, release, environment, maxBreadcrumbs = 15 } = opts;
  const ignoreErrors = opts.ignoreErrors ?? [];

  // DSN shape: https://<publicKey>@<host>/<projectId>. The public key
  // authenticates ingest (sent as ?sentry_key) — the draft client dropped it,
  // which is why GlitchTip rejected its events.
  const parsed = dsn.match(/^https:\/\/(.+?)@(.+?)\/(\d+)\/?$/);
  if (!parsed) {
    // No silent fallback: a malformed DSN is a config error worth surfacing.
    console.error('[glitchtip] invalid DSN, error reporting disabled:', dsn);
    return;
  }
  const [, publicKey, host, projectId] = parsed;
  const url = `https://${host}/api/${projectId}/envelope/?sentry_key=${publicKey}&sentry_version=7`;

  const breadcrumbs: Breadcrumb[] = [];
  let lastSig: string | null = null;

  const storeOffline = (body: string) => {
    try {
      const q = JSON.parse(
        localStorage.getItem(OFFLINE_KEY) || '[]',
      ) as string[];
      q.push(body);
      localStorage.setItem(OFFLINE_KEY, JSON.stringify(q.slice(-10)));
    } catch {
      // localStorage unavailable/full — dropping the event is acceptable.
    }
  };

  const send = (body: string) => {
    // keepalive lets the POST outlive a page unload (errors thrown on navigation).
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-sentry-envelope' },
      body,
      keepalive: true,
    }).catch(() => storeOffline(body));
  };

  const flush = () => {
    try {
      const q = JSON.parse(
        localStorage.getItem(OFFLINE_KEY) || '[]',
      ) as string[];
      localStorage.removeItem(OFFLINE_KEY);
      q.forEach(send);
    } catch {
      // Nothing buffered or storage unavailable.
    }
  };

  const capture = (raw: unknown, ctx?: CaptureContext) => {
    const error = toError(raw);
    if (matchesAny(error.message, ignoreErrors)) return;

    // Cheap consecutive-dedupe: stops a single throw that hits two handlers
    // (e.g. window.onerror + Vue) — or an error loop — from spamming ingest.
    const sig = `${error.message}::${(error.stack || '').slice(0, 80)}`;
    if (sig === lastSig) return;
    lastSig = sig;

    const id = crypto.randomUUID().replace(/-/g, '');
    const event = {
      event_id: id,
      timestamp: Date.now() / 1000,
      platform: 'javascript',
      level: ctx?.level ?? 'error',
      release,
      environment,
      breadcrumbs: { values: breadcrumbs.slice() },
      exception: {
        values: [
          {
            type: error.name || 'Error',
            value: error.message || String(error),
            stacktrace: parseStack(error.stack),
            mechanism: {
              type: ctx?.mechanism ?? 'generic',
              handled: ctx?.handled ?? true,
            },
          },
        ],
      },
      extra: ctx?.extra,
    };

    // Sentry envelope = 3 newline-delimited JSON lines: envelope header, item
    // header, item payload. The draft client omitted the item header line,
    // which made GlitchTip reject the whole envelope.
    const body =
      JSON.stringify({ event_id: id, sent_at: new Date().toISOString(), dsn }) +
      '\n' +
      JSON.stringify({ type: 'event' }) +
      '\n' +
      JSON.stringify(event);
    send(body);
  };

  const breadcrumb = (message: string, category = 'app') => {
    breadcrumbs.push({ timestamp: Date.now() / 1000, message, category });
    if (breadcrumbs.length > maxBreadcrumbs) breadcrumbs.shift();
  };

  client = { capture, breadcrumb };
  flush();
}

// No-ops until initGlitchTip runs (no DSN → no reporting), so callers never
// need to null-check.
export function captureError(error: unknown, ctx?: CaptureContext): void {
  client?.capture(error, ctx);
}

export function addBreadcrumb(message: string, category?: string): void {
  client?.breadcrumb(message, category);
}
