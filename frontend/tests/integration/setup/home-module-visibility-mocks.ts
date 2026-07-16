/**
 * HTTP-boundary mocks for the "module deactivation greys out the module in
 * the calculator view" spec (Issue #1403, slice c) — extended to also cover
 * a module with no computed stats at all ("not started"), which must
 * likewise render greyed-out rather than being omitted from the chart.
 * Single source of truth for the enabled/greyed decision is
 * `isModuleFullyAvailable` (src/composables/useModuleAvailability.ts),
 * shared with Results and the backoffice Reporting page.
 *
 * Unlike ``data-management-mocks.ts`` we do NOT set
 * ``__LIGHTHOUSE_BYPASS__``: ``workspaceGuard`` returns early on that flag
 * and never populates ``moduleStore.state.emissionBreakdown`` /
 * ``yearConfigStore.config`` — and ``HomePage``'s module-icon-axis chart
 * only renders once ``hasValidatedData`` is true, which reads the
 * emission-breakdown store. So the real guards must run, same rationale as
 * ``simulator-mocks.ts``.
 *
 * The single aggregate endpoint (``GET /workspace/{unit}/{year}/home``)
 * hydrates both the year-configuration store (module enabled/disabled) and
 * the emission-breakdown store (which categories render as icons) in one
 * response — see ``workspaceGuard.ts`` / ``loadWorkspaceFromRoute``.
 */
import type { Page } from '@playwright/test';

export const HOME_URL = '/en/10/2024/home';

const MOCK_USER = {
  id: 1,
  email: 'test@example.com',
  display_name: 'Test User',
  institutional_id: 'test-user',
  roles_raw: [],
  // Grant edit on all three modules under test so config (enabled/disabled)
  // and stats presence are the only things differing between the icons —
  // isolates each grey-out reason from permission gating.
  permissions: {
    'modules.process_emissions': ['view', 'edit'],
    'modules.equipment': ['view', 'edit'],
    'modules.external_cloud_and_ai': ['view', 'edit'],
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

/**
 * Register the mocks and drive the home page to a state where the
 * module-carbon-footprint chart's icon axis renders with one disabled
 * (process-emissions, module_type_id 8) and one enabled (equipment,
 * module_type_id 4) module.
 */
export async function mockHomeBackend(page: Page): Promise<void> {
  // Catch-all registered FIRST = lowest priority under Playwright's LIFO
  // route evaluation, so it only absorbs calls the specific routes below
  // don't claim (workspace selector bar units refresh, i18n discovery, …).
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({ status: 404, body: '' }),
  );

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

  await page.route(/.*\/api\/v1\/workspace\/10\/2024\/home$/, (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        carbon_report_id: 42,
        year_config: {
          year: 2024,
          is_started: true,
          configuration_completed: '2024-01-01T00:00:00Z',
          config: {
            modules: {
              // process-emissions — disabled in the back-office.
              '8': {
                enabled: false,
                uncertainty_tag: 'medium',
                incomplete: false,
                submodules: {},
              },
              // equipment — enabled, has stats.
              '4': {
                enabled: true,
                uncertainty_tag: 'medium',
                incomplete: false,
                submodules: {},
              },
              // external-cloud-and-ai — enabled, but never touched: no entry
              // in module_breakdown below, so it has no computed stats at
              // all ("not started"). Must still render, greyed out.
              '7': {
                enabled: true,
                uncertainty_tag: 'medium',
                incomplete: false,
                submodules: {},
              },
            },
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
          recalculation_status: [],
          updated_at: '2024-01-01T00:00:00Z',
        },
        // Raw persisted-stats shape (`ReportStats` in emissionStatsAdapter.ts)
        // — workspaceGuard adapts this via toEmissionBreakdown() itself. A
        // bucket's mere presence (regardless of its emissions detail) is what
        // makes `isModuleFullyAvailable`'s `hasStats` true for that category;
        // `external_cloud_and_ai` has no bucket at all, so it renders as "not
        // started" / greyed out.
        stats: {
          buckets: {
            process_emissions: {
              scope: 1,
              additional: false,
              total_kg: 3000,
              by_emission_type: {},
            },
            equipment: {
              scope: 2,
              additional: false,
              total_kg: 2000,
              by_emission_type: {},
            },
          },
          per_fte: {},
          // Non-empty so HomePage's ``hasValidatedData`` renders the chart
          // instead of the empty "ready to start" state.
          validated_buckets: ['process_emissions', 'equipment'],
          total_fte: 0,
          total_tonnes_validated_co2eq: 5,
        },
      }),
    });
  });
}
