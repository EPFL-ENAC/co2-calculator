/**
 * HTTP-boundary mocks for the workspace year-selector regression suite
 * (issue #1558 — a year opened via the backoffice "Open year for users"
 * button doesn't appear in the calculator's year dropdown until a hard
 * reload).
 *
 * Mirrors ``simulator-mocks.ts``: ``__LIGHTHOUSE_BYPASS__`` is NOT set
 * because it short-circuits ``loadWorkspaceFromRoute`` before it ever calls
 * ``fetchConfiguredYears`` — the exact call this suite is regression-testing.
 * The real guards run against a mocked ``GET /session`` + per-endpoint
 * mocks instead.
 *
 * Two units (10 and 20) let a test trigger a genuine in-app navigation (a
 * unit switch via the WorkspaceSelectorBar) that changes the route's
 * ``:unit`` param and re-runs ``loadWorkspaceFromRoute`` — without that,
 * there is no user-reachable way to force the guard to re-run while staying
 * within a single already-loaded unit/year, and the whole point of this bug
 * is that it repros on in-app navigation, not full reload.
 *
 * IMPORTANT — Playwright 1.60 uses LIFO route evaluation: the LAST
 * registered handler is evaluated FIRST. Catch-alls must be registered
 * FIRST so they have the LOWEST priority.
 */
import type { Page } from '@playwright/test';

export const WORKSPACE_URL = '/en/10-unit-alpha/2024/home';

const MOCK_USER = {
  id: 1,
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

const UNIT_B = {
  id: 20,
  name: 'Unit Beta',
  institutional_id: 'unit-20',
  principal_user_id: 'user-1',
  principal_user_function: 'Test',
  principal_user_name: 'Test User',
  affiliations: [],
  current_user_role: 'principal',
};

// Raw persisted-stats shape (`ReportStats` in emissionStatsAdapter.ts) —
// workspaceGuard adapts this via toEmissionBreakdown() itself. All-empty:
// this suite only cares about the year dropdown, not computed totals.
function buildReportStats() {
  return {
    buckets: {},
    per_fte: {},
    validated_buckets: [],
    total_fte: 0,
  };
}

/**
 * ``GET /year-configuration/`` list payload. 2024 is open from the start;
 * 2025 exists (already configured by the backoffice) but only becomes
 * ``is_started`` once the test calls ``openYear2025ForUsers()`` — mirroring
 * clicking "Open year for users" in another tab/session.
 */
function buildConfiguredYears(year2025Started: boolean) {
  return [
    {
      year: 2024,
      is_started: true,
      configuration_completed: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    {
      year: 2025,
      is_started: year2025Started,
      configuration_completed: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
  ];
}

export interface MockWorkspaceBackend {
  requests: Array<{ method: string; url: string }>;
  /** Flip year 2025's `is_started` flag, as the backoffice "Open year for users" button would. */
  openYear2025ForUsers: () => void;
}

export async function mockWorkspaceBackend(
  page: Page,
): Promise<MockWorkspaceBackend> {
  const requests: Array<{ method: string; url: string }> = [];
  let year2025Started = false;

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

  // Year-configuration list — hit by `fetchConfiguredYears()`. This is the
  // endpoint issue #1558's fix makes the workspace guard call on every run
  // instead of only once (when `configuredYears` was empty).
  await page.route(/.*\/api\/v1\/year-configuration\/$/, (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildConfiguredYears(year2025Started)),
    });
  });

  // Workspace-home aggregate for both units/years reachable in the test.
  await page.route(
    /.*\/api\/v1\/workspace\/(10|20)\/(2024|2025)\/home$/,
    (route) => {
      const match = route
        .request()
        .url()
        .match(/workspace\/(\d+)\/\d+\/home/);
      const unitId = match?.[1] === '20' ? 20 : 10;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          carbon_report_id: unitId === 20 ? 43 : 42,
          year_config: null,
          stats: buildReportStats(),
        }),
      });
    },
  );

  // Session — authGuard calls bootstrap() on /session. Registered LAST =
  // highest priority (first evaluated in LIFO).
  await page.route(/.*\/api\/v1\/session$/, (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: MOCK_USER,
          units: [UNIT_A, UNIT_B],
          // Only 2024 is open at bootstrap time — matches the real
          // scenario where the user logs in before the admin opens 2025.
          configured_years: buildConfiguredYears(false),
        }),
      });
    }
    return route.continue();
  });

  return {
    requests,
    openYear2025ForUsers: () => {
      year2025Started = true;
    },
  };
}
