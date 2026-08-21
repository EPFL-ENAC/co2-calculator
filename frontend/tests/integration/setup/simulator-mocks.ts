/**
 * HTTP-boundary mocks for the simulator-explore Playwright suite.
 *
 * Unlike the data-management suite, we do NOT set ``__LIGHTHOUSE_BYPASS__``
 * because ``validateUnitGuard`` returns early when it sees the flag and
 * never sets ``selectedUnit`` / ``selectedYear``.  ``SimulationExplorePage``
 * accesses ``workspaceStore.selectedUnit!.id`` in onMounted, which throws a
 * TypeError when selectedUnit is null — making the page untestable with the
 * bypass flag.
 *
 * Instead we mock the minimal API surface (session, units, carbon-reports,
 * year-configuration) so the real guards run, set up workspace state, and
 * the page renders normally.
 *
 * IMPORTANT — Playwright 1.60 uses LIFO route evaluation: the LAST registered
 * handler is evaluated FIRST.  Catch-alls must be registered FIRST so they
 * have the LOWEST priority.  Specific routes registered AFTER override them.
 */

import type { Page } from '@playwright/test';

export const SIMULATOR_URL = '/en/10/2024/simulation/explore/sim-1';

const MOCK_USER = {
  id: 1,
  email: 'test@example.com',
  display_name: 'Test User',
  institutional_id: 'test-user',
  roles_raw: [],
  // Global edit permission for headcount + professional-travel so both the
  // member form and the plane/train traveler dropdown are shown.
  permissions: {
    'modules.headcount': ['view', 'edit'],
    'modules.professional_travel': ['view', 'edit'],
  },
};

const MOCK_UNIT = {
  id: 10,
  name: '10',
  institutional_id: 'unit-10',
  principal_user_id: 'user-1',
  principal_user_function: 'Test',
  principal_user_name: 'Test User',
  affiliations: [],
  current_user_role: 'principal',
};

// Regular (non-simulator) carbon report — used by validateUnitGuard.
const MOCK_CARBON_REPORT = {
  id: 42,
  unit_id: 10,
  year: 2024,
  carbon_project_id: 1,
};

// Simulator explore carbon report — created/fetched by onMounted.
const MOCK_SIMULATOR_REPORT = {
  id: 99,
  unit_id: 10,
  year: 2024,
  carbon_project_id: 1,
};

function buildModuleTotalsResponse(
  moduleType: string,
  data_entry_types_total_items: Record<number, number>,
) {
  return {
    module_type: moduleType,
    unit: 10,
    year: '2024',
    data_entry_types_total_items,
    carbon_report_module_id: 100,
    retrieved_at: '2024-01-01T00:00:00Z',
    submodules: {},
    totals: { total_submodules: 0, total_items: 0 },
  };
}

function buildSubmoduleResponse(items: object[]) {
  return {
    id: 'member',
    name: 'member',
    items,
    summary: {
      total_items: items.length,
      annual_consumption_kwh: 0,
      total_kg_co2eq: 0,
    },
  };
}

// Traveler-dropdown payload
// (GET /carbon-reports/{reportId}/modules/headcount/members).
// Shape differs from the submodule list: a flat array of {institutional_id, name}.
function buildMembersDropdown(memberPosted: boolean) {
  return memberPosted
    ? [{ institutional_id: 'sciper-1', name: 'Test Member' }]
    : [];
}

// Raw persisted-stats shape (`ReportStats` in emissionStatsAdapter.ts) — the
// backend contract since 0bc63cd1 replaced the plain /emission-breakdown
// route with /report-stats + client-side toEmissionBreakdown(). A single
// `food` bucket carries the whole total so toEmissionBreakdown's totalKg sum
// resolves to totalTonnesCo2eq without needing per-emission-type detail.
function buildReportStats(totalTonnesCo2eq: number) {
  return {
    buckets:
      totalTonnesCo2eq > 0
        ? {
            food: {
              scope: 3,
              additional: false,
              total_kg: totalTonnesCo2eq * 1000,
              by_emission_type: {},
            },
          }
        : {},
    per_fte: {},
    validated_buckets: [],
    total_fte: 0,
  };
}

/**
 * Register all HTTP mocks for the simulator-explore page.
 *
 * Returns a request log for post-test assertions.  A single ``memberPosted``
 * flag drives the stateful mocks: the headcount count response and the
 * emission-breakdown response both change on the second call (after the
 * POST to headcount/member).
 *
 * Route registration order follows Playwright 1.60 LIFO semantics:
 * catch-alls are registered FIRST (lowest priority) and specific routes
 * are registered LAST (highest priority / evaluated first).
 */
export async function mockSimulatorBackend(page: Page): Promise<{
  requests: Array<{ method: string; url: string; body?: string }>;
}> {
  const requests: Array<{ method: string; url: string; body?: string }> = [];

  // Track whether a member entry has been POSTed so stateful mocks can
  // return the updated counts / breakdown on subsequent GET calls.
  let memberPosted = false;
  // Track explore report creation so the get-or-create GET flips to 200.
  let exploreReportCreated = false;

  page.on('request', (req) => {
    if (req.url().includes('/api/v1/')) {
      requests.push({
        method: req.method(),
        url: req.url(),
        body: req.postData() ?? undefined,
      });
    }
  });

  // ─── STEP 1: Register catch-alls first (lowest priority in LIFO) ──────────

  // Absorb any remaining /api/v1/ calls (e.g. year-configuration list,
  // validated-totals probes) without crashing the app.
  await page.route('**/api/v1/**', (route) => {
    return route.fulfill({ status: 404, body: '' });
  });

  // ─── STEP 2: Register specific routes last (highest priority in LIFO) ─────

  // Taxonomy — ModuleTable calls getSubmoduleTaxonomy when expanded.
  await page.route('**/api/v1/taxonomies/**', (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ name: '', label: '', children: [] }),
    });
  });

  // Print/explore page's fetchAllData batches taxonomy fetches as one
  // .../data-entries call per module instead of one per submodule
  // (#2049 T6) — returns a map keyed by entry, not one TaxonomyNode.
  // Registered after the catch-all above so LIFO picks this more
  // specific route first for that path.
  await page.route('**/api/v1/taxonomies/module/*/data-entries*', (route) => {
    const entries = new URL(route.request().url()).searchParams.getAll(
      'entries',
    );
    const body = Object.fromEntries(
      entries.map((entry) => [entry, { name: entry, label: '', children: [] }]),
    );
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });

  // All other module preview_limit=0 calls (non-headcount modules).
  // Identity-addressed by the explore report id (99).
  await page.route(
    /.*\/api\/v1\/carbon-reports\/99\/modules\/[^/?]+\?.*preview_limit/,
    (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildModuleTotalsResponse('unknown', {})),
      });
    },
  );

  // Report stats for the simulator report (id=99) — stateful. Backs
  // moduleStore.getEmissionBreakdown(), which fetches raw buckets and
  // adapts them client-side via toEmissionBreakdown().
  await page.route(/.*\/api\/v1\/modules-stats\/99\/report-stats/, (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildReportStats(memberPosted ? 5 : 0)),
    });
  });

  // Headcount module totals (preview_limit=0) — stateful.
  // \? ensures this only matches the module endpoint, NOT /headcount/member.
  await page.route(
    /.*\/api\/v1\/carbon-reports\/99\/modules\/headcount\?/,
    (route) => {
      const totals = memberPosted ? { 1: 1, 2: 0 } : { 1: 0, 2: 0 };
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildModuleTotalsResponse('headcount', totals)),
      });
    },
  );

  // headcount/member submodule — POST (create entry) + GET (list items).
  await page.route(
    /.*\/api\/v1\/carbon-reports\/99\/modules\/headcount\/member/,
    (route) => {
      if (route.request().method() === 'POST') {
        memberPosted = true;
        return route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, name: 'Test Member', fte: 0.5 }),
        });
      }
      // GET — return 0 items initially, 1 item after POST.
      const items = memberPosted
        ? [{ id: 1, name: 'Test Member', fte: 0.5 }]
        : [];
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildSubmoduleResponse(items)),
      });
    },
  );

  // Traveler dropdown (headcount/members) — stateful. Registered AFTER the
  // headcount/member route so its higher LIFO priority wins for the trailing
  // "s". Returns [] before a member is posted, [Test Member] after. The
  // assertion side also checks this hits the explore report id (99) so the
  // simulator reads its own report, not the calculator's.
  await page.route(
    /.*\/api\/v1\/carbon-reports\/99\/modules\/headcount\/members/,
    (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMembersDropdown(memberPosted)),
      });
    },
  );

  // Simulator explore carbon report — stateful get-or-create. GET 404 until
  // the page POSTs to create it, then GET returns the report so identity
  // addressing (resolveCarbonReportId, explore branch) can resolve id=99 for
  // the module calls that follow.
  await page.route(
    /.*\/api\/v1\/carbon-reports\/simulator\/explore\/unit\/10\/reference-year\/2024\//,
    (route) => {
      if (route.request().method() === 'POST') {
        exploreReportCreated = true;
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_SIMULATOR_REPORT),
        });
      }
      // GET
      if (!exploreReportCreated) {
        return route.fulfill({ status: 404, body: '' });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_SIMULATOR_REPORT),
      });
    },
  );

  // Year configuration GET for a specific year — return 404 so all
  // submodules are visible (yearConfig.config stays null).
  await page.route(/.*\/api\/v1\/year-configuration\/\d+$/, (route) => {
    return route.fulfill({ status: 404, body: '' });
  });

  // Module states — validateUnitGuard → fetchModuleStates(42).
  await page.route(/.*\/api\/v1\/carbon-reports\/42\/modules\/$/, (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '[]',
    });
  });

  // Regular carbon report — validateUnitGuard → selectCarbonReportForYear.
  await page.route(
    /.*\/api\/v1\/carbon-reports\/unit\/10\/year\/2024\/$/,
    (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CARBON_REPORT),
      });
    },
  );

  // Users/units — validateUnitGuard calls getUnits().
  await page.route(/.*\/api\/v1\/users\/units$/, (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([MOCK_UNIT]),
    });
  });

  // Workspace-home aggregate — workspaceGuard calls fetchWorkspaceHome().
  // Minimal payload: report id + year config + raw stats (workspaceGuard
  // adapts it via toEmissionBreakdown() itself). SimulationExplorePage
  // overwrites this with its own report-stats fetch for report id=99 right
  // after mount, so the exact values here don't matter — only that the
  // shape doesn't throw inside toEmissionBreakdown().
  await page.route(/.*\/api\/v1\/workspace\/10\/2024\/home$/, (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        carbon_report_id: MOCK_CARBON_REPORT.id,
        year_config: null,
        stats: buildReportStats(0),
      }),
    });
  });

  // Session — authGuard calls bootstrap() on /session, which now returns the
  // user plus workspace context (units + configured years).
  // Registered LAST = highest priority (first evaluated in LIFO).
  await page.route(/.*\/api\/v1\/session$/, (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: MOCK_USER,
          units: [MOCK_UNIT],
          configured_years: [],
        }),
      });
    }
    return route.continue();
  });

  return { requests };
}
