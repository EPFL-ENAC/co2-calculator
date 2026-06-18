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
  // Structured context sections (e.g. `{ vue: { componentName, … } }`), each
  // rendered as its own panel in GlitchTip alongside browser/os/device.
  contexts?: Record<string, Record<string, unknown>>;
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

// Compact, never-throwing string for a non-Error value (rejected object,
// number, etc.) so its content survives into the report.
function describeNonError(raw: unknown): string {
  try {
    return typeof raw === 'object' && raw !== null
      ? JSON.stringify(raw)
      : String(raw);
  } catch {
    // Circular/unserializable — fall back to the type tag, e.g. [object Object].
    return Object.prototype.toString.call(raw);
  }
}

// Normalize anything thrown (Error, string, ErrorEvent.message, rejection
// reason) into an Error so we always have name/message/stack to report.
function toError(raw: unknown): Error {
  if (raw instanceof Error) return raw;
  if (typeof raw === 'string') return new Error(raw);
  // Objects with a string `message` (DOMException, custom error-likes).
  const message = (raw as { message?: unknown } | null)?.message;
  if (typeof message === 'string' && message) return new Error(message);
  // True non-Error rejection: keep the payload instead of "Unknown error",
  // and tag it distinctly so GlitchTip groups these apart from real Errors.
  const err = new Error(
    `Non-Error rejection: ${describeNonError(raw).slice(0, 200)}`,
  );
  err.name = 'NonError';
  return err;
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

    // A real Error carries a stack from its throw/reject site. Anything else
    // (string, rejected object/number) only gets the stack we synthesize here
    // at capture time — flag it so the trace reads as synthetic, not real.
    const synthetic = !(raw instanceof Error);

    const id = crypto.randomUUID().replace(/-/g, '');
    const event = {
      event_id: id,
      timestamp: Date.now() / 1000,
      platform: 'javascript',
      level: ctx?.level ?? 'error',
      release,
      environment,
      // GlitchTip parses the User-Agent server-side into browser/os/device
      // tags (+ icons) — the same way the Sentry SDK gets them. We just have
      // to ship the header in the request context.
      request: {
        url: location.href,
        headers: { 'User-Agent': navigator.userAgent },
      },
      breadcrumbs: { values: breadcrumbs.slice() },
      contexts: ctx?.contexts,
      exception: {
        values: [
          {
            type: error.name || 'Error',
            value: error.message || String(error),
            stacktrace: parseStack(error.stack),
            mechanism: {
              type: ctx?.mechanism ?? 'generic',
              handled: ctx?.handled ?? true,
              ...(synthetic ? { synthetic: true } : {}),
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
  installInstrumentation(breadcrumb, host);
  flush();
}

// Auto-record the actions leading up to a crash — the Sentry SDK's default
// breadcrumbs (fetch, console, ui.click; navigation is wired from the router
// in boot/sentry.ts). Installed once, best-effort: a wrapper must never throw
// into the app's own fetch/console.
let instrumented = false;
function installInstrumentation(
  record: (message: string, category: string) => void,
  ingestHost: string,
): void {
  if (instrumented) return;
  instrumented = true;

  // fetch — covers all ky/API traffic. Skip our own ingest POSTs (else every
  // captured error spawns a self-referential breadcrumb).
  const origFetch = window.fetch.bind(window);
  window.fetch = (...args: Parameters<typeof fetch>) => {
    const [input, init] = args;
    const url =
      typeof input === 'string'
        ? input
        : input instanceof Request
          ? input.url
          : String(input);
    const method = (
      init?.method ?? (input instanceof Request ? input.method : 'GET')
    ).toUpperCase();
    const promise = origFetch(...args);
    if (!url.includes(ingestHost)) {
      promise.then(
        (res) => record(`${method} ${url} [${res.status}]`, 'fetch'),
        () => record(`${method} ${url} [failed]`, 'fetch'),
      );
    }
    return promise;
  };

  // console.error / warn — the signals devs already emit when things go wrong.
  (['error', 'warn'] as const).forEach((level) => {
    const orig = console[level].bind(console);
    console[level] = (...args: unknown[]) => {
      record(
        args
          .map((a) => String(a))
          .join(' ')
          .slice(0, 200),
        'console',
      );
      orig(...args);
    };
  });

  // ui.click — capture phase, so we still see it if a handler stops propagation.
  window.addEventListener(
    'click',
    (e) => {
      if (e.target instanceof Element) {
        record(describeTarget(e.target), 'ui.click');
      }
    },
    { capture: true, passive: true },
  );
}

// Compact CSS-ish description of a clicked element for the breadcrumb trail,
// e.g. `button#save.btn.primary "Save changes"`.
function describeTarget(el: Element): string {
  const sel = [el.tagName.toLowerCase()];
  if (el.id) sel.push(`#${el.id}`);
  const cls =
    typeof el.className === 'string'
      ? el.className.trim().split(/\s+/).filter(Boolean).slice(0, 2)
      : [];
  if (cls.length) sel.push('.' + cls.join('.'));
  const text = (el.textContent ?? '').trim().slice(0, 30);
  return text ? `${sel.join('')} "${text}"` : sel.join('');
}

// No-ops until initGlitchTip runs (no DSN → no reporting), so callers never
// need to null-check.
export function captureError(error: unknown, ctx?: CaptureContext): void {
  client?.capture(error, ctx);
}

export function addBreadcrumb(message: string, category?: string): void {
  client?.breadcrumb(message, category);
}
