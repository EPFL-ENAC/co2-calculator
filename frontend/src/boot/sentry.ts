import { boot } from 'quasar/wrappers';
import * as Sentry from '@sentry/vue';
import { Notify } from 'quasar';
import { HTTPError } from 'ky';
import { runtimeConfig } from 'src/config/runtime';

// Errors that are not actionable (browser quirks, user-driven aborts).
// Sentry drops events whose message matches any of these.
const ignoreErrors: (string | RegExp)[] = [
  // Harmless browser-bug noise from libraries that observe element sizes.
  // See https://github.com/vuejs/vue-cli/issues/7431
  'ResizeObserver loop limit exceeded',
  'ResizeObserver loop completed with undelivered notifications',
  // Network noise: user navigated away, lost connection, cancelled fetch.
  'NetworkError',
  'AbortError',
  'Failed to fetch',
  // Media element auto-aborted by browser when the user navigates.
  "The fetching process for the media resource was aborted by the user agent at the user's request.",
];

// Toast helper. Centralized so the three handlers below stay readable.
// Uses `color: 'negative'` to match the existing convention in api/http.ts.
function notifyError(message: string, caption?: string) {
  Notify.create({
    color: 'negative',
    message,
    caption,
    position: 'top',
    timeout: 5000,
    actions: [{ icon: 'close', color: 'white' }],
  });
}

export default boot(({ app, router }) => {
  const { sentryDsn, environment, release } = runtimeConfig;

  if (sentryDsn) {
    Sentry.init({
      app,
      dsn: sentryDsn,
      environment,
      release,
      ignoreErrors,
      integrations: [
        // Auto-instruments vue-router navigations + fetch/XHR as Sentry
        // transactions. This is what gives GlitchTip "slow route" visibility.
        Sentry.browserTracingIntegration({ router }),
      ],
      // Same bundle hits dev/stage/prod via runtime DSN, so this rate applies
      // everywhere. 5% balances signal on rare slow routes against GlitchTip
      // ingestion cost.
      tracesSampleRate: 0.05,
      // Only attach trace headers (sentry-trace, baggage) to our own backend.
      // Never propagate to third-party endpoints (CDNs, analytics) — they'll
      // reject CORS preflights and pollute their logs.
      tracePropagationTargets: ['localhost', /^\/api\//],
    });
  }

  // -------------------------------------------------------------------------
  // Vue-level uncaught errors.
  //
  // Fires for errors thrown inside component lifecycle hooks, watchers,
  // computeds, etc. @sentry/vue's `app: Vue` option already wires
  // captureException here; we layer a Notify toast so users see *something*
  // when a render fails instead of a silent broken UI.
  // -------------------------------------------------------------------------
  const previousVueHandler = app.config.errorHandler;
  app.config.errorHandler = (err, instance, info) => {
    if (typeof previousVueHandler === 'function') {
      previousVueHandler(err, instance, info);
    }
    if (import.meta.env.DEV) {
      console.error('[vue errorHandler]', err, info);
    }
    notifyError(
      err instanceof Error ? err.message : String(err),
      info, // e.g. "render", "mounted hook"
    );
  };

  // -------------------------------------------------------------------------
  // Browser-level synchronous errors.
  //
  // Catches errors thrown outside Vue (third-party libs, setTimeout callbacks,
  // event handlers attached directly to DOM). Sentry auto-captures these via
  // its global handler; we add ResizeObserver suppression and a user-facing
  // toast.
  // -------------------------------------------------------------------------
  window.addEventListener('error', (event) => {
    if (event.message?.includes('ResizeObserver loop')) {
      // Browser bug, not a real failure. Stop propagation so neither Sentry
      // nor the toast layer treats it as one.
      event.stopImmediatePropagation();
      event.stopPropagation();
      event.preventDefault();
      return;
    }
    if (import.meta.env.DEV) {
      console.error('[window error]', event.error ?? event.message);
    }
    notifyError(
      event.message || 'Unknown error',
      `${event.filename}:${event.lineno}:${event.colno}`,
    );
  });

  // -------------------------------------------------------------------------
  // Unhandled promise rejections.
  //
  // Sentry auto-captures the reason. We skip notifying when the reason is a
  // ky HTTPError — api/http.ts's afterResponse hook already toasted it, and
  // double-toasting is worse than missing one.
  // -------------------------------------------------------------------------
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    if (reason instanceof HTTPError) {
      return;
    }
    if (import.meta.env.DEV) {
      console.error('[unhandledrejection]', reason);
    }
    const message =
      reason instanceof Error
        ? reason.message
        : (reason?.message as string | undefined) ??
          String(reason ?? 'Unhandled rejection');
    notifyError(message);
  });
});
