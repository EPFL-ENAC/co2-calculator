/**
 * Shared HTTP-boundary + EventSource mocks for the back-office
 * data-management Playwright suite (Unit 10/11).
 *
 * The page sits behind a permission guard but both ``authGuard`` and
 * ``permissionGuard`` honor ``window.__LIGHTHOUSE_BYPASS__`` — so we set
 * that flag instead of mocking the user object, which keeps each test
 * self-contained and removes any coupling to the auth store shape.
 *
 * HTTP is mocked via ``page.route`` per endpoint.  SSE cannot be —
 * ``new EventSource(...)`` opens a real socket that bypasses
 * ``page.route`` — so we override ``window.EventSource`` in
 * ``addInitScript`` and expose a controller on ``window.__sse`` so each
 * spec can drive ``message`` / ``pipeline-update`` events deterministically.
 */
import type { BrowserContext, Page, Route } from '@playwright/test';

/** Default backoffice landing URL with explicit year. */
export const DATA_MANAGEMENT_URL = '/en/back-office/data-management?year=2024';

/**
 * Issue #867 — fixed pipeline_id returned by the create-year mock so
 * specs can reference it when emitting fake SSE events via
 * ``window.__sse.emit(...)``.  Any UUID-shaped string works; this one
 * is recognizable in test failures.
 */
export const TEST_PIPELINE_ID = '00000000-0000-4000-8000-000000000867';

/** Wire shape of the year-configuration response. */
export interface YearConfigBuilderOptions {
  year: number;
  /**
   * Per ``module_type_id`` recalculation status.  Default is empty so
   * the "Recalculation needed" / "Recalculate" affordance is hidden,
   * which is the steady state for all but the recalc tests.
   */
  recalculationStatus?: Array<{
    module_type_id: number;
    needs_recalculation: boolean;
    data_entry_types?: Array<{
      data_entry_type_id: number;
      needs_recalculation: boolean;
    }>;
  }>;
  /**
   * Override module config entries.  Defaults make Headcount complete
   * (member submodule has a SUCCESS factor + data job) so test 6 can
   * see the recalc button.  Other modules stay incomplete; that's
   * fine — the tests target Headcount specifically.
   */
  modulesOverride?: Record<string, unknown>;
}

const SUCCESS_FACTOR_JOB = {
  job_id: 1001,
  module_type_id: 1,
  data_entry_type_id: 1,
  year: 2024,
  ingestion_method: 1,
  target_type: 1,
  state: 3,
  result: 0,
  status_message: 'ok',
  meta: { rows_processed: 10, file_path: '/uploads/factors.csv' },
};

const SUCCESS_DATA_JOB = {
  job_id: 1002,
  module_type_id: 1,
  data_entry_type_id: 1,
  year: 2024,
  ingestion_method: 1,
  target_type: 0,
  state: 3,
  result: 0,
  status_message: 'ok',
  meta: { rows_processed: 5, file_path: '/uploads/data.csv' },
};

/**
 * Build a year-configuration payload that satisfies the page's render
 * gates — Headcount module fully complete with SUCCESS factor + data
 * jobs on submodule ``member`` (moduleTypeId 1, dataEntryTypeId 1).
 *
 * Tests that need a different shape pass ``modulesOverride`` /
 * ``recalculationStatus``.
 */
export function buildYearConfig(options: YearConfigBuilderOptions) {
  const baseHeadcount = {
    enabled: true,
    uncertainty_tag: 'medium',
    submodules: {
      // member — required factor + data both SUCCESS so isModuleIncomplete=false
      '1': {
        enabled: true,
        threshold: null,
        latest_factor_job: SUCCESS_FACTOR_JOB,
        latest_data_job: SUCCESS_DATA_JOB,
      },
      // student — noData=true, only factor required
      '2': {
        enabled: true,
        threshold: null,
        latest_factor_job: SUCCESS_FACTOR_JOB,
      },
    },
  };

  return {
    year: options.year,
    is_started: false,
    // Year-config gate (#1234 follow-up `13616a35`): the data-management
    // page refuses to render the upload UI until ``configuration_completed``
    // is non-null (set by ``unit_sync_handler`` on SUCCESS).  Default
    // satisfies the gate so upload/dispatch happy-path tests aren't
    // blocked; tests that want to exercise the unprovisioned state
    // can pass an explicit override via ``onGetYearConfig``.
    configuration_completed: '2024-01-01T00:00:00Z',
    config: {
      modules: options.modulesOverride ?? { '1': baseHeadcount },
      reduction_objectives: {
        files: {
          institutional_footprint: null,
          population_projections: null,
          unit_scenarios: null,
        },
        goals: [],
        institutional_footprint: [],
        population_projections: [],
        unit_scenarios: [],
      },
    },
    recalculation_status: options.recalculationStatus ?? [],
    updated_at: '2024-01-01T00:00:00Z',
  };
}

/**
 * Install the EventSource shim + Lighthouse bypass + localStorage
 * reset.  Call ONCE per test before ``page.goto`` — Playwright re-runs
 * init scripts on every page load.
 *
 * The shim swallows ``new EventSource(url)`` so the SUT's pipeline /
 * job stream subscriptions don't hit a non-existent backend.  Current
 * happy-path tests don't need to drive events; should that change,
 * extend the shim with a ``window.__sse`` controller and re-export
 * ``emit`` / ``emitTo`` helpers (see git history for prior shape).
 */
export async function installInitScripts(
  context: BrowserContext,
): Promise<void> {
  await context.addInitScript(() => {
    // Bypass authGuard + permissionGuard.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).__LIGHTHOUSE_BYPASS__ = true;

    // Clear pinia-plugin-persistedstate residue from previous tests
    // (key ``filesLocalStorage`` lives on ``localStorage``).
    try {
      localStorage.clear();
    } catch {
      // Some pages run before ``localStorage`` is reachable; ignore.
    }

    // Issue #867 / Plan 310 — registry of live FakeEventSource
    // instances, keyed by the pipeline_id segment of the URL.  Tests
    // can drive ``pipeline-update`` events deterministically via
    // ``window.__sse.emit(pipelineId, payload)`` instead of waiting on
    // a real SSE socket.
    interface FakeSseRegistry {
      sources: Map<string, FakeEventSource>;
      emit: (pipelineId: string, payload: unknown) => void;
    }

    class FakeEventSource extends EventTarget {
      url: string;
      readyState = 1;
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;
      onopen: ((ev: Event) => void) | null = null;
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSED = 2;

      constructor(url: string) {
        super();
        this.url = url;
        // ``/api/v1/sync/pipelines/{id}/stream`` → extract id segment.
        const match = url.match(/\/sync\/pipelines\/([^/]+)\/stream/);
        if (match) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const reg = (window as any).__sse as FakeSseRegistry | undefined;
          if (reg) reg.sources.set(match[1]!, this);
        }
      }

      close() {
        this.readyState = 2;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const reg = (window as any).__sse as FakeSseRegistry | undefined;
        if (reg) {
          // ``forEach`` instead of ``for...of`` so the file compiles
          // under tsconfig ``target=es5`` without ``downlevelIteration``.
          reg.sources.forEach((source, id) => {
            if (source === this) reg.sources.delete(id);
          });
        }
      }
    }

    const registry: FakeSseRegistry = {
      sources: new Map(),
      emit(pipelineId, payload) {
        const source = this.sources.get(pipelineId);
        if (!source) return;
        const evt = new MessageEvent('pipeline-update', {
          data: JSON.stringify(payload),
        });
        source.dispatchEvent(evt);
      },
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).__sse = registry;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).EventSource = FakeEventSource;
  });
}

/**
 * Default HTTP routes for the data-management page.  Tests that need
 * different behavior (e.g., 404 on year-configuration to reach the
 * "Create year" card) override the relevant routes BEFORE calling
 * this — first matching ``page.route`` wins.
 */
export interface RouteOverrides {
  /** Override the year-configuration GET response. */
  onGetYearConfig?: (route: Route, year: number) => Promise<void> | void;
  /** Override active-pipelines response. */
  onActivePipelines?: (
    route: Route,
    moduleIds: number[],
  ) => Promise<void> | void;
  /**
   * Override active-pipelines/year/{year} response (Issue #867 —
   * year-level pipelines).  Default returns ``[]`` (no live year-level
   * chain) which matches the steady state.
   */
  onYearLevelActivePipelines?: (
    route: Route,
    year: number,
  ) => Promise<void> | void;
  /** Override sync/units POST. */
  onSyncUnits?: (route: Route) => Promise<void> | void;
  /** Override files/temp-upload POST. */
  onTempUpload?: (route: Route) => Promise<void> | void;
  /** Override sync/dispatch POST. */
  onSyncDispatch?: (route: Route) => Promise<void> | void;
  /** Override recalculate-emissions POST. */
  onRecalculateEmissions?: (route: Route) => Promise<void> | void;
  /** Override sync/factors POST (computed factors). */
  onSyncFactors?: (route: Route) => Promise<void> | void;
  /** Override year-configuration POST (create year). */
  onCreateYear?: (route: Route) => Promise<void> | void;
  /** Override year-configuration PATCH (e.g., flip is_started). */
  onUpdateYear?: (route: Route, year: number) => Promise<void> | void;
}

/**
 * Stand up the default mock server.  Returns the request log so tests
 * can assert exact URLs / methods after interactions.
 */
export async function mockBackend(
  page: Page,
  overrides: RouteOverrides = {},
): Promise<{
  requests: Array<{ method: string; url: string; body?: string }>;
}> {
  const requests: Array<{ method: string; url: string; body?: string }> = [];

  // Catch-all logger to surface unexpected calls in failure output.
  page.on('request', (req) => {
    if (req.url().includes('/api/v1/')) {
      requests.push({
        method: req.method(),
        url: req.url(),
        body: req.postData() ?? undefined,
      });
    }
  });

  // auth/me — 401 so getUser() resolves to null without crashing.
  // The Lighthouse bypass means we never read user.value, so 401 is
  // safe (and matches the production "not yet logged in" state).
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ status: 401, body: '' }),
  );

  // year-configuration GET / POST / PATCH
  await page.route(/.*\/api\/v1\/year-configuration\/(\d+)$/, async (route) => {
    const url = new URL(route.request().url());
    const year = parseInt(url.pathname.split('/').pop() ?? '0', 10);
    const method = route.request().method();
    if (method === 'GET') {
      if (overrides.onGetYearConfig) {
        await overrides.onGetYearConfig(route, year);
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildYearConfig({ year })),
      });
      return;
    }
    if (method === 'POST') {
      if (overrides.onCreateYear) {
        await overrides.onCreateYear(route);
        return;
      }
      // Issue #867 — the real backend returns a fresh ``pipeline_id``
      // on create so the page can subscribe to the unit_sync SSE
      // stream immediately.  Mirror that here so tests exercising the
      // post-create flow see the same shape; tests that don't care
      // can ignore the field.
      const body = {
        ...buildYearConfig({ year }),
        pipeline_id: TEST_PIPELINE_ID,
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      });
      return;
    }
    if (method === 'PATCH') {
      if (overrides.onUpdateYear) {
        await overrides.onUpdateYear(route, year);
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildYearConfig({ year })),
      });
      return;
    }
    await route.fallback();
  });

  // active-pipelines/year/{year} — empty list by default (no live
  // year-level pipeline).  Issue #867 reload-rehydrate path.
  // Registered BEFORE the module-scoped catch-all so this more
  // specific URL pattern wins for ``…/active-pipelines/year/2025``.
  await page.route(
    /.*\/api\/v1\/sync\/active-pipelines\/year\/(\d+)$/,
    async (route) => {
      const url = new URL(route.request().url());
      const year = parseInt(url.pathname.split('/').pop() ?? '0', 10);
      if (overrides.onYearLevelActivePipelines) {
        await overrides.onYearLevelActivePipelines(route, year);
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]',
      });
    },
  );

  // active-pipelines — empty by default (no recalculating badge).
  await page.route('**/api/v1/sync/active-pipelines**', async (route) => {
    if (overrides.onActivePipelines) {
      const url = new URL(route.request().url());
      const modules =
        url.searchParams
          .get('modules')
          ?.split(',')
          .map((s) => parseInt(s, 10)) ?? [];
      await overrides.onActivePipelines(route, modules);
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{}',
    });
  });

  // sync/units (Accred sync trigger)
  await page.route('**/api/v1/sync/units', async (route) => {
    if (overrides.onSyncUnits) {
      await overrides.onSyncUnits(route);
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"status":"started"}',
    });
  });

  // files/temp-upload (CSV pre-upload step)
  await page.route('**/api/v1/files/temp-upload', async (route) => {
    if (overrides.onTempUpload) {
      await overrides.onTempUpload(route);
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          name: 'data.csv',
          path: '/tmp/data.csv',
          size: 100,
          mime_type: 'text/csv',
        },
      ]),
    });
  });

  // sync/dispatch (CSV/API ingestion entry point)
  await page.route('**/api/v1/sync/dispatch', async (route) => {
    if (overrides.onSyncDispatch) {
      await overrides.onSyncDispatch(route);
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ job_id: 9001 }),
    });
  });

  // sync/jobs/year/{year}/latest (used by previous-year copy lookup
  // inside the dialog).  Empty list keeps the UI simple.
  await page.route(
    /.*\/api\/v1\/sync\/jobs\/year\/\d+\/latest$/,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]',
      });
    },
  );

  // sync/recalculate-emissions/{moduleTypeId}[ /{dataEntryTypeId} ]
  await page.route(
    /.*\/api\/v1\/sync\/recalculate-emissions\/[^/?]+(\/[^/?]+)?\??/,
    async (route) => {
      if (overrides.onRecalculateEmissions) {
        await overrides.onRecalculateEmissions(route);
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 9100 }),
      });
    },
  );

  // sync/factors/{moduleTypeId}/{dataEntryTypeId}
  await page.route(
    /.*\/api\/v1\/sync\/factors\/[^/?]+\/[^/?]+\??/,
    async (route) => {
      if (overrides.onSyncFactors) {
        await overrides.onSyncFactors(route);
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 9200 }),
      });
    },
  );

  // sync/pipelines/{id} — one-shot snapshot read.  Return null-shaped
  // empty so the seed step is a no-op; the SSE shim is what drives
  // updates.
  await page.route(/.*\/api\/v1\/sync\/pipelines\/[^/]+$/, async (route) => {
    const url = route.request().url();
    const pipelineId = url.split('/').pop() ?? '';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ pipeline_id: pipelineId, jobs: [] }),
    });
  });

  return { requests };
}
