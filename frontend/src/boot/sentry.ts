import { boot } from 'quasar/wrappers';
import { Notify } from 'quasar';
import { HTTPError } from 'ky';
import { runtimeConfig } from 'src/config/runtime';
import { captureError, initGlitchTip } from 'src/utils/glitchtip';

// Errors that are not actionable (browser quirks, user-driven aborts).
// captureError() drops events whose message matches any of these.
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

// Toast helper. Uses `color: 'negative'` to match api/http.ts.
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

  // Init is a no-op without a DSN (dev, CI Lighthouse, unconfigured deploys),
  // so the handlers below simply report nowhere in those environments.
  if (sentryDsn) {
    initGlitchTip({ dsn: sentryDsn, release, environment, ignoreErrors });
  }

  // -------------------------------------------------------------------------
  // Vue-level uncaught errors: thrown inside component lifecycle hooks,
  // watchers, computeds, render, etc. We report them and layer a toast so
  // users see *something* when a render fails instead of a silent broken UI.
  // -------------------------------------------------------------------------
  const previousVueHandler = app.config.errorHandler;
  app.config.errorHandler = (err, instance, info) => {
    if (typeof previousVueHandler === 'function') {
      previousVueHandler(err, instance, info);
    }
    captureError(err, { mechanism: 'vue', extra: { info } });
    if (import.meta.env.DEV) {
      console.error('[vue errorHandler]', err, info);
    }
    notifyError(
      err instanceof Error ? err.message : String(err),
      info, // e.g. "render", "mounted hook"
    );
  };

  // -------------------------------------------------------------------------
  // Vue Router errors: failed dynamic-import of a route chunk, errors thrown
  // in navigation guards/resolvers. These never reach the Vue error handler.
  // -------------------------------------------------------------------------
  router.onError((err) => {
    captureError(err, { mechanism: 'vue-router' });
  });

  // -------------------------------------------------------------------------
  // Browser-level synchronous errors: thrown outside Vue (third-party libs,
  // setTimeout callbacks, DOM event handlers). Suppress ResizeObserver noise
  // entirely; report and toast everything else.
  // -------------------------------------------------------------------------
  window.addEventListener('error', (event) => {
    if (event.message?.includes('ResizeObserver loop')) {
      // Browser bug, not a real failure. Stop propagation so nothing treats it
      // as one.
      event.stopImmediatePropagation();
      event.stopPropagation();
      event.preventDefault();
      return;
    }
    captureError(event.error ?? event.message, { mechanism: 'onerror' });
    if (import.meta.env.DEV) {
      console.error('[window error]', event.error ?? event.message);
    }
    notifyError(
      event.message || 'Unknown error',
      `${event.filename}:${event.lineno}:${event.colno}`,
    );
  });

  // -------------------------------------------------------------------------
  // Unhandled promise rejections. We still report ky HTTPErrors (an unhandled
  // one means a caller forgot to await/catch — worth knowing) but skip the
  // toast: api/http.ts's afterResponse hook already toasted it, and
  // double-toasting is worse than missing one.
  // -------------------------------------------------------------------------
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    captureError(reason, {
      mechanism: 'onunhandledrejection',
      handled: false,
    });
    if (reason instanceof HTTPError) {
      return;
    }
    if (import.meta.env.DEV) {
      console.error('[unhandledrejection]', reason);
    }
    const message =
      reason instanceof Error
        ? reason.message
        : ((reason?.message as string | undefined) ??
          String(reason ?? 'Unhandled rejection'));
    notifyError(message);
  });
});
