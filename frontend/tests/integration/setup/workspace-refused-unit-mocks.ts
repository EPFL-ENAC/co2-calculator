/**
 * HTTP-boundary mocks for the refused-workspace regression suite (#2570).
 *
 * Mirrors ``workspace-year-refresh-mocks.ts``: no ``__LIGHTHOUSE_BYPASS__``,
 * because it short-circuits ``loadWorkspaceFromRoute`` before it reaches the
 * calls this suite is about. The real guards run against a mocked
 * ``GET /session`` plus per-endpoint mocks.
 *
 * The scenario is a stale persisted workspace selection — the shape every
 * returning user had after the dev/stage database was dropped and reseeded:
 * ``workspaceLocalStorage`` still names a unit that the user may READ but may
 * not ENTER. Hence the asymmetry below, which is the whole bug:
 *
 *   GET /units/996                 -> 200  (readable)
 *   GET /workspace/996/2025/home   -> 403  (not enterable)
 *
 * IMPORTANT — Playwright 1.60 uses LIFO route evaluation: the LAST registered
 * handler is evaluated FIRST. Catch-alls must be registered FIRST so they have
 * the LOWEST priority.
 */
import type { Page } from '@playwright/test';

/** The stale selection: unit 996 is readable but its workspace is refused. */
export const STALE_WORKSPACE_URL = '/en/996-stale-unit/2025/home';
/** Where the guard's soft redirect must land: the user's own first unit. */
export const EXPECTED_URL_PATTERN = /\/10-unit-alpha\/2025\/home/;

const MOCK_USER = {
  id: 4,
  email: 'test@example.com',
  display_name: 'Test User',
  institutional_id: 'test-user',
  roles_raw: [],
  permissions: {},
};

const UNIT_A = {
  id: 10,
  name: 'Unit Alpha',
  institutional_id: 'unit-10',
  principal_user_id: 'user-1',
  principal_user_function: 'Test',
  principal_user_name: 'Test User',
  affiliations: [],
  current_user_role: 'principal',
};

/** Readable but not enterable — the unit the stale selection points at. */
const UNIT_STALE = {
  ...UNIT_A,
  id: 996,
  name: 'Stale Unit',
  institutional_id: 'unit-996',
};

function buildReportStats() {
  return { buckets: {}, per_fte: {}, validated_buckets: [], total_fte: 0 };
}

function buildConfiguredYears() {
  return [
    {
      year: 2025,
      is_started: true,
      configuration_completed: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
  ];
}

export interface RefusedWorkspaceBackend {
  requests: Array<{ method: string; url: string }>;
}

export async function mockRefusedWorkspaceBackend(
  page: Page,
): Promise<RefusedWorkspaceBackend> {
  const requests: Array<{ method: string; url: string }> = [];

  page.on('request', (req) => {
    if (req.url().includes('/api/v1/')) {
      requests.push({ method: req.method(), url: req.url() });
    }
  });

  // ─── STEP 1: catch-all first (lowest LIFO priority) ────────────────────
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({ status: 404, body: '' }),
  );

  // ─── STEP 2: specific routes after (highest LIFO priority) ─────────────
  await page.route(/.*\/api\/v1\/year-configuration\/$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildConfiguredYears()),
    }),
  );

  // The unit probe the guard falls back to for a non-member unit (#2369).
  // 200: the user may read it. This is what makes validateUnit() succeed and
  // lets navigation reach the workspace call below.
  await page.route(/.*\/api\/v1\/units\/996$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(UNIT_STALE),
    }),
  );

  // The real authorization boundary, and the refusal under test. The body
  // mirrors the backend's permission-denied shape, because api/http.ts parses
  // it to build the /unauthorized query string — a bare body would not
  // exercise the same branch.
  await page.route(/.*\/api\/v1\/workspace\/996\/2025\/home$/, (route) =>
    route.fulfill({
      status: 403,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: 'Permission denied: workspace.read required',
      }),
    }),
  );

  // The user's own unit — where the guard's soft redirect must land.
  await page.route(/.*\/api\/v1\/workspace\/10\/2025\/home$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        carbon_report_id: 42,
        year_config: null,
        stats: buildReportStats(),
      }),
    }),
  );

  // Session — authGuard calls bootstrap(). Registered LAST = evaluated first.
  // The membership list holds ONLY unit 10: unit 996 is deliberately absent,
  // which is what sends validateUnit() down the backend-probe path.
  await page.route(/.*\/api\/v1\/session$/, (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: MOCK_USER,
          units: [UNIT_A],
          configured_years: buildConfiguredYears(),
        }),
      });
    }
    return route.continue();
  });

  return { requests };
}
