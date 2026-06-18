import { boot } from 'quasar/wrappers';
import { Notify } from 'quasar';
import { HTTPError } from 'ky';
import type { ComponentPublicInstance } from 'vue';
import { runtimeConfig } from 'src/config/runtime';
import { i18n } from 'src/boot/i18n';
import {
  addBreadcrumb,
  captureError,
  initGlitchTip,
  startNavigationTrace,
} from 'src/utils/glitchtip';

// Shallow (depth-1) copy of a component's props for the report: nested values
// collapse to "[Object]" / "[Array]". Avoids circular refs (which would make
// JSON.stringify throw on the whole event) and giant payloads — matches what
// @sentry/vue sends.
function shallowProps(
  props: Record<string, unknown> | undefined,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(props ?? {})) {
    out[key] =
      value === null || typeof value !== 'object'
        ? value
        : Array.isArray(value)
          ? '[Array]'
          : '[Object]';
  }
  return out;
}

// The `contexts.vue` panel GlitchTip renders: which component threw, in which
// lifecycle hook, with which props — the @sentry/vue equivalent.
function vueErrorContext(
  instance: ComponentPublicInstance | null,
  info: string,
): Record<string, unknown> {
  const type = instance?.$?.type as
    | { name?: string; __name?: string }
    | undefined;
  return {
    componentName: type?.name || type?.__name || 'Anonymous Component',
    lifecycleHook: info,
    propsData: shallowProps(instance?.$props),
  };
}

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

// A route's lazy chunk (or its CSS) failed to load. After a deploy, clients
// holding an old index.html request hashed chunks that no longer exist on the
// server — the dynamic import rejects. Messages differ per engine, hence the
// broad match (WebKit: "Importing a module script failed."; Chromium: "Failed
// to fetch dynamically imported module"; Firefox/Vite variants below).
function isChunkLoadError(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err);
  return (
    /Failed to fetch dynamically imported module/i.test(message) ||
    /error loading dynamically imported module/i.test(message) ||
    /Importing a module script failed/i.test(message) ||
    /Unable to preload CSS/i.test(message) ||
    /Loading chunk \S+ failed/i.test(message)
  );
}

// Persistent "reload to get the new version" prompt. Guarded so a burst of
// chunk errors (one per failed prefetch) shows a single toast. We prompt
// rather than auto-reload to avoid clobbering unsaved work.
let reloadPromptShown = false;
function notifyReloadOnce() {
  if (reloadPromptShown) return;
  reloadPromptShown = true;
  Notify.create({
    color: 'info',
    message: i18n.global.t('new_version_available'),
    position: 'top',
    timeout: 0, // sticky until the user acts
    actions: [
      {
        label: i18n.global.t('reload'),
        color: 'white',
        handler: () => window.location.reload(),
      },
    ],
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
    captureError(err, {
      mechanism: 'vue',
      contexts: { vue: vueErrorContext(instance, info) },
    });
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
  // A chunk-load failure is usually a stale client after a deploy, not a code
  // bug — surface a reload prompt so the user can recover in one click.
  // -------------------------------------------------------------------------
  router.onError((err) => {
    captureError(err, { mechanism: 'vue-router' });
    if (isChunkLoadError(err)) {
      notifyReloadOnce();
    }
  });

  // Navigation breadcrumbs: the "how did the user get here" trail attached to
  // any later crash. Also start a fresh trace so errors on the new page group
  // under one trace_id. No-op until a DSN is configured.
  router.afterEach((to, from) => {
    startNavigationTrace();
    addBreadcrumb(`${from.fullPath} → ${to.fullPath}`, 'navigation');
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

  // -------------------------------------------------------------------------
  // Dev-only manual trigger: `window.__gtTest('<kind>')` from the console to
  // fire each error path and confirm it reaches GlitchTip. Stripped from prod
  // builds by the import.meta.env.DEV guard (dead-code eliminated).
  // -------------------------------------------------------------------------
  if (import.meta.env.DEV) {
    const triggers: Record<string, () => void> = {
      // Real trace (Error captured at the throw site).
      throw: () =>
        setTimeout(() => {
          throw new Error('[__gtTest] thrown error');
        }, 0),
      // Real trace (Error captured at the reject site).
      reject: () => void Promise.reject(new Error('[__gtTest] rejected Error')),
      // No origin trace exists → reported as a synthetic "NonError".
      'reject-nonerror': () =>
        void Promise.reject({ code: 'E_TEST', detail: 'plain object payload' }),
      // Direct capture, e.g. the path api/http.ts uses for HTTP 5xx.
      capture: () =>
        captureError(new Error('[__gtTest] manual capture'), {
          mechanism: 'manual',
          extra: { hint: 'this is what the ky 5xx path sends' },
        }),
      // Stale-chunk router error → also shows the reload prompt.
      chunk: () => {
        captureError(new Error('Importing a module script failed.'), {
          mechanism: 'vue-router',
        });
        notifyReloadOnce();
      },
    };
    (window as unknown as { __gtTest: (kind?: string) => void }).__gtTest = (
      kind = 'throw',
    ) => {
      const run = triggers[kind];
      if (!run) {
        console.warn(`[__gtTest] kinds: ${Object.keys(triggers).join(' | ')}`);
        return;
      }
      run();
      console.log(`[__gtTest] fired "${kind}"`);
    };
  }
});
