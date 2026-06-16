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
  // Global edit permission for headcount so the member form is shown.
  permissions: {
    'modules.headcount': ['view', 'edit'],
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

function buildEmissionBreakdown(totalTonnesCo2eq: number) {
  return {
    module_breakdown: [],
    total_tonnes_co2eq: totalTonnesCo2eq,
    additional_breakdown: [],
    per_person_breakdown: {},
    validated_categories: [],
    headcount_validated: false,
    buildings_validated: false,
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

  // All other module preview_limit=0 calls (non-headcount modules).
  await page.route(
    /.*\/api\/v1\/modules\/10\/2024\/[^/?]+\?.*preview_limit/,
    (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildModuleTotalsResponse('unknown', {})),
      });
    },
  );

  // Emission breakdown for the simulator report (id=99) — stateful.
  await page.route(
    /.*\/api\/v1\/modules-stats\/99\/emission-breakdown/,
    (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildEmissionBreakdown(memberPosted ? 5 : 0)),
      });
    },
  );

  // Headcount module totals (preview_limit=0) — stateful.
  // \? ensures this only matches the module endpoint, NOT /headcount/member.
  await page.route(
    /.*\/api\/v1\/modules\/10\/2024\/headcount\?/,
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
    /.*\/api\/v1\/modules\/10\/2024\/headcount\/member/,
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

  // Simulator explore carbon report — GET 404, POST creates it.
  await page.route(
    /.*\/api\/v1\/carbon-reports\/simulator\/explore\/unit\/10\/reference-year\/2024\//,
    (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({ status: 404, body: '' });
      }
      if (route.request().method() === 'POST') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_SIMULATOR_REPORT),
        });
      }
      return route.continue();
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

  // Session — authGuard calls getUser() on /session.
  // Registered LAST = highest priority (first evaluated in LIFO).
  await page.route(/.*\/api\/v1\/session$/, (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_USER),
      });
    }
    return route.continue();
  });

  return { requests };
}
