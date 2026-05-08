/**
 * Plan 310 / Issue #310 — shared HTTP-boundary mocks for the back-office
 * data-management Playwright suite.
 *
 * Two responsibilities:
 *
 * 1. Inject a stub ``window.EventSource`` BEFORE the SPA bundle boots
 *    so ``usePipelineStream`` ends up wired to a controllable shim
 *    (the composable's ``__setEventSourceImpl`` test seam is
 *    bundle-internal and unreachable from a Playwright e2e context).
 *    The shim captures every ``new EventSource(url)`` into a global
 *    map keyed by URL and exposes ``dispatch(eventName, payload)``
 *    per instance — tests drive the SSE timeline via ``page.evaluate``.
 *
 * 2. Stub the small set of HTTP endpoints DataManagementPage hits on
 *    mount so navigation reaches a fully-rendered ``ModuleConfig``
 *    without a backend dev server.  The active-pipelines mock is
 *    closure-controlled so tests can flip its return mid-flow without
 *    re-registering the route handler.
 *
 * Unit 10 may extend this file as new data-management specs land —
 * the helpers here are deliberately additive (each ``installX`` is a
 * one-shot setup; extra routes can stack on the same ``page``).
 */

import type { Page } from '@playwright/test';

/**
 * Wire shape for ``GET /api/v1/sync/active-pipelines?year=Y&modules=...``.
 * Sparse: only modules with an active pipeline are present.
 */
export type ActivePipelinesResponse = Record<string, string>;

/**
 * Test-side handle to a single SSE pipe (one ``new EventSource`` call).
 * ``page.evaluate`` retrieves the live shim instance via
 * ``window.__ssePipes.get(url)`` and ``dispatch`` re-fires
 * ``addEventListener`` callbacks.
 */
export interface SsePipe {
  url: string;
  // The shim object is created in page context; tests call its
  // ``dispatch`` from ``page.evaluate``.  Typed as ``unknown`` here to
  // discourage Node-side use.
  __pageContext: unknown;
}

/**
 * Install a controllable EventSource shim into the page BEFORE the
 * SPA bundle loads.  Also sets ``__LIGHTHOUSE_BYPASS__`` so the
 * router auth/permission guards let the back-office route through.
 *
 * MUST be called before ``page.goto``.  ``addInitScript`` runs on
 * every navigation, including the initial one, before any in-page
 * script — that's the only way to capture the ``EventSource``
 * constructor (``usePipelineStream`` calls it eagerly inside the
 * Vue ``setup``).
 */
export async function installPlaywrightTestShims(page: Page): Promise<void> {
  await page.addInitScript(() => {
    // 1. Auth bypass — router guards short-circuit when this is set.
    //    The page still renders ``DataManagementPage`` and ``ModuleConfig``
    //    against whatever the HTTP route mocks return.
    (
      window as Window & { __LIGHTHOUSE_BYPASS__?: boolean }
    ).__LIGHTHOUSE_BYPASS__ = true;

    // 2. EventSource shim.
    //    ``usePipelineStream`` wires listeners only for ``pipeline-update``
    //    (and the heartbeat ``ping``) — implementing the full WHATWG
    //    EventSource contract is overkill.  The shim:
    //      - stores itself in ``window.__ssePipes`` (Map<url, instance>)
    //      - implements ``addEventListener`` / ``removeEventListener`` /
    //        ``close``
    //      - exposes ``dispatch(eventName, payload)`` for tests
    //
    //    Tests pull the instance out of the map and call ``dispatch``
    //    to simulate a backend SSE event with the parsed-JSON payload
    //    matching ``PipelineUpdate``.
    interface ShimSse extends EventSource {
      __listeners: Record<string, ((ev: MessageEvent) => void)[]>;
      __closed: boolean;
      dispatch(eventName: string, payload: unknown): void;
    }
    type SsePipeMap = Map<string, ShimSse>;
    const pipes: SsePipeMap = new Map();
    (window as Window & { __ssePipes?: SsePipeMap }).__ssePipes = pipes;

    class FakeEventSource {
      url: string;
      readyState = 0; // CONNECTING
      onopen: ((ev: Event) => void) | null = null;
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;
      __listeners: Record<string, ((ev: MessageEvent) => void)[]> = {};
      __closed = false;

      constructor(url: string) {
        this.url = url;
        // Match the production EventSource: open is async.  Schedule
        // the OPEN transition on a microtask so the calling code can
        // attach listeners before any event fires.
        queueMicrotask(() => {
          this.readyState = 1; // OPEN
          if (this.onopen) this.onopen(new Event('open'));
        });
        pipes.set(url, this as unknown as ShimSse);
      }

      addEventListener(
        eventName: string,
        cb: (ev: MessageEvent) => void,
      ): void {
        if (!this.__listeners[eventName]) {
          this.__listeners[eventName] = [];
        }
        this.__listeners[eventName].push(cb);
      }

      removeEventListener(
        eventName: string,
        cb: (ev: MessageEvent) => void,
      ): void {
        const list = this.__listeners[eventName];
        if (!list) return;
        const idx = list.indexOf(cb);
        if (idx >= 0) list.splice(idx, 1);
      }

      close(): void {
        this.__closed = true;
        this.readyState = 2; // CLOSED
        pipes.delete(this.url);
      }

      /**
       * Test-only — re-fire every registered listener for ``eventName``
       * with a synthetic MessageEvent whose ``data`` is the JSON-stringified
       * payload (the production listener calls ``JSON.parse(event.data)``).
       */
      dispatch(eventName: string, payload: unknown): void {
        if (this.__closed) return;
        const list = this.__listeners[eventName] ?? [];
        const ev = new MessageEvent(eventName, {
          data: typeof payload === 'string' ? payload : JSON.stringify(payload),
        });
        for (const cb of list) cb(ev);
      }
    }

    // Replace the native constructor.  Keep the static constants
    // attached so ``readyState`` comparisons in production code keep
    // resolving to the right values (defensive — usePipelineStream
    // doesn't read them today, but a future caller might).
    const Native = (window as Window & { EventSource?: typeof EventSource })
      .EventSource;
    (FakeEventSource as unknown as { CONNECTING: number }).CONNECTING = 0;
    (FakeEventSource as unknown as { OPEN: number }).OPEN = 1;
    (FakeEventSource as unknown as { CLOSED: number }).CLOSED = 2;
    (
      window as Window & { EventSource: unknown; __NativeEventSource?: unknown }
    ).EventSource = FakeEventSource;
    (window as Window & { __NativeEventSource?: unknown }).__NativeEventSource =
      Native;

    // 3. Clipboard mirror.
    //    Headless chromium accepts the ``clipboard-write`` permission
    //    grant but the resulting write doesn't always flow back through
    //    ``navigator.clipboard.readText()`` reliably across the
    //    Playwright transport.  Hijack
    //    ``Clipboard.prototype.writeText`` (the prototype is shared
    //    by every ``navigator.clipboard`` instance) and mirror the
    //    value into ``window.__clipboard`` so the spec asserts off
    //    the deterministic mirror instead of fighting transport
    //    quirks.  Quasar's ``copyToClipboard`` also has an
    //    ``execCommand`` fallback when ``navigator.clipboard`` is
    //    undefined; we leave clipboard defined so the prototype
    //    patch is what runs.
    type ClipMirror = { value: string };
    const mirror: ClipMirror = { value: '' };
    (window as Window & { __clipboard?: ClipMirror }).__clipboard = mirror;
    if (
      typeof Clipboard !== 'undefined' &&
      Clipboard.prototype &&
      typeof Clipboard.prototype.writeText === 'function'
    ) {
      const original = Clipboard.prototype.writeText;
      Clipboard.prototype.writeText = function (
        this: Clipboard,
        text: string,
      ): Promise<void> {
        mirror.value = text;
        try {
          return original.call(this, text);
        } catch {
          return Promise.resolve();
        }
      };
    }
  });
}

/**
 * Build the minimal year-configuration response that lets
 * DataManagementPage render the Headcount module card (moduleTypeId = 1).
 *
 * Only ``recalculation_status`` matters for the badge tests (we drive
 * everything else via the active-pipelines + SSE pipes).  The module
 * config bag is intentionally minimal — ``ModuleConfig.vue`` reads the
 * ``recalculation_status`` map but happily renders against an empty
 * submodule list.
 */
export function buildYearConfigResponse(year: number): unknown {
  return {
    year,
    is_started: false,
    is_reports_synced: false,
    config: {
      modules: {
        '1': {
          enabled: true,
          uncertainty_tag: 'medium',
          submodules: {},
          latest_common_data_job: null,
          latest_common_factor_job: null,
        },
      },
      reduction_objectives: {},
    },
    recalculation_status: [
      {
        module_type_id: 1,
        year,
        needs_recalculation: false,
        data_entry_types: [],
      },
    ],
    updated_at: new Date(year, 0, 1).toISOString(),
  };
}

/**
 * Closure-controlled wrapper around the active-pipelines route handler.
 * Tests get back a setter so they can flip the response mid-flow
 * (e.g. simulate the post-stream-close refetch returning ``{}`` after
 * having returned ``{1: <uuid>}`` initially).
 */
export interface ActivePipelinesController {
  set(response: ActivePipelinesResponse): void;
}

/**
 * Register a closure-controlled mock for
 * ``GET /api/v1/sync/active-pipelines?...``.  Initial state is the
 * empty map (no active pipelines), matching the steady state.
 */
export async function mockActivePipelines(
  page: Page,
): Promise<ActivePipelinesController> {
  let current: ActivePipelinesResponse = {};
  await page.route('**/api/v1/sync/active-pipelines*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(current),
    });
  });
  return {
    set(response) {
      current = response;
    },
  };
}

/**
 * Register the per-pipeline snapshot mock — ``GET /api/v1/sync/pipelines/{id}``
 * (NOT the ``/stream`` suffix).  ``usePipelineStream`` calls this once
 * before opening the SSE stream to seed initial state; the test
 * normally just returns an empty job list and lets the SSE events
 * drive the store.
 */
export async function mockPipelineSnapshot(
  page: Page,
  options: {
    /** Override the default ``{pipeline_id, jobs: []}`` response. */
    response?: (pipelineId: string) => unknown;
    /** Return 5xx for the error-path test. */
    status?: number;
  } = {},
): Promise<void> {
  await page.route(/\/api\/v1\/sync\/pipelines\/[^/]+$/, async (route) => {
    const url = new URL(route.request().url());
    const pipelineId = url.pathname.split('/').pop() ?? '';
    if (options.status && options.status >= 500) {
      await route.fulfill({
        status: options.status,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'mocked snapshot failure' }),
      });
      return;
    }
    const body = options.response?.(pipelineId) ?? {
      pipeline_id: pipelineId,
      jobs: [],
    };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
}

/**
 * Stub the SSE stream HTTP endpoint.  This catches the request that
 * the FAKE EventSource constructor would normally fire on its way to
 * the wire — but since we replaced ``EventSource`` itself with a shim
 * that never opens a real connection, this route is a defensive
 * fallback (e.g. for the error-path test where we WANT the production
 * EventSource to see a 5xx).
 */
export async function mockPipelineStream(
  page: Page,
  options: { status?: number } = {},
): Promise<void> {
  await page.route(
    /\/api\/v1\/sync\/pipelines\/[^/]+\/stream$/,
    async (route) => {
      if (options.status && options.status >= 500) {
        await route.fulfill({
          status: options.status,
          contentType: 'text/plain',
          body: 'mocked stream failure',
        });
        return;
      }
      // Default: empty SSE response — the shim is doing the real work.
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: '',
      });
    },
  );
}

/**
 * Catch-all guard for any ``/api/**`` request the suite did not
 * explicitly stub.  Returns 200 ``{}`` so the page never trips a
 * production ``Notify`` toast on an unmocked endpoint.  Routes
 * registered ABOVE this one win (Playwright matches in registration
 * order, last-registered first).  Call this LAST.
 */
export async function mockApiCatchAll(page: Page): Promise<void> {
  await page.route('**/api/**', async (route) => {
    const url = route.request().url();
    // Auth-me: return a permissive identity so any code path that
    // bypasses the LIGHTHOUSE_BYPASS guard (e.g. components reading
    // the auth store directly) still has something to chew on.
    if (url.includes('/auth/me')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          email: 'test@example.com',
          roles_raw: [{ role: 'admin' }],
          permissions: [],
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{}',
    });
  });
}

/**
 * Convenience: wire every default mock + the test shims in one call.
 *
 * Playwright matches routes in REVERSE registration order (most-recent
 * first), so the catch-all has to be registered FIRST — every specific
 * route registered after it gets first-match priority.  Tests that
 * need bespoke responses should layer their ``page.route`` calls
 * AFTER this returns; their handlers will then win against everything
 * registered here.
 */
export async function setupDataManagementMocks(
  page: Page,
  year: number,
): Promise<{ activePipelines: ActivePipelinesController }> {
  await installPlaywrightTestShims(page);
  // Register most-general first; the specific routes layered below
  // win because page.route matches last-registered first.
  await mockApiCatchAll(page);
  await page.route(`**/api/v1/year-configuration/${year}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildYearConfigResponse(year)),
    });
  });
  const activePipelines = await mockActivePipelines(page);
  await mockPipelineSnapshot(page);
  await mockPipelineStream(page);
  return { activePipelines };
}

/**
 * Compute the year DataManagementPage will land on by default — the
 * page picks ``currentYear - 1`` from a hardcoded ``MIN_YEARS=2024``
 * sequence.  Centralized here so specs don't drift if the page logic
 * changes.
 */
export function defaultSelectedYear(): number {
  return new Date().getFullYear() - 1;
}
