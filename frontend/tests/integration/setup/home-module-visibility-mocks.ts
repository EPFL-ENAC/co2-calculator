/**
 * HTTP-boundary mocks for the "module deactivation greys out the module in
 * the calculator view" spec (Issue #1403, slice c).
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
  // Grant edit on both modules under test so config (enabled/disabled) is
  // the only thing that differs between the two icons — isolates the
  // "module deactivation greys it out" behavior from permission gating.
  permissions: {
    'modules.process_emissions': ['view', 'edit'],
    'modules.equipment': ['view', 'edit'],
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
              // equipment — enabled.
              '4': {
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
        emission_breakdown: {
          module_breakdown: [
            { category: 'process_emissions', emissions: [] },
            { category: 'equipment', emissions: [] },
          ],
          total_tonnes_co2eq: 5,
          total_tonnes_validated_co2eq: 5,
          additional_breakdown: [],
          per_person_breakdown: {},
          // Non-empty so HomePage's ``hasValidatedData`` renders the chart
          // instead of the empty "ready to start" state.
          validated_categories: ['process_emissions', 'equipment'],
          headcount_validated: false,
          buildings_validated: false,
          total_fte: 0,
          module_states: [],
        },
      }),
    });
  });
}
