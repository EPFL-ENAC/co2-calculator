/**
 * HTTP-boundary mocks for the Home chart icon-axis greying rules
 * (Issue #1403 slice c, reworked for #2443): a module icon is greyed out
 * ONLY when the user lacks view/edit access, hidden ONLY when the module is
 * deactivated in the back-office — module status (validated or not) and
 * data presence never grey an icon. Single source of truth for the
 * enabled/greyed decision is `isModuleFullyAvailable`
 * (src/composables/useModuleAvailability.ts).
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
  // Access to every module under test EXCEPT professional_travel — its
  // icon must render greyed out (missing access is the only grey-out
  // reason left after #2443).
  permissions: {
    'modules.process_emissions': ['view', 'edit'],
    'modules.equipment': ['view', 'edit'],
    'modules.external_cloud_and_ai': ['view', 'edit'],
    'modules.purchase': ['view', 'edit'],
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
 * Register the mocks. The scenario exercises every icon-axis rule at once:
 *  - process-emissions (8): back-office disabled → hidden from the chart
 *    (even though it has stats and is validated);
 *  - equipment (4): enabled, access, validated with stats → clickable;
 *  - external-cloud-and-ai (7): enabled, access, VALIDATED but no stats
 *    bucket → clickable (the #2443 regression);
 *  - purchase (5): enabled, access, not started (no stats, not validated)
 *    → clickable;
 *  - professional-travel (2): enabled, validated with stats, but the user
 *    has NO access → greyed out.
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
              // professional-travel — enabled; the user has no access.
              '2': {
                enabled: true,
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
              // purchase — enabled, never touched (no bucket, not validated).
              '5': {
                enabled: true,
                uncertainty_tag: 'medium',
                incomplete: false,
                submodules: {},
              },
              // external-cloud-and-ai — enabled and validated, but with no
              // stats bucket below (#2443).
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
        // — workspaceGuard adapts this via toEmissionBreakdown() itself.
        // Neither a bucket's presence nor membership in validated_buckets
        // may influence icon greying: `external_cloud_and_ai` is validated
        // with NO bucket (#2443) and `purchases` has neither, yet both
        // render clickable; `professional_travel` has both, yet renders
        // greyed (no access).
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
            professional_travel: {
              scope: 3,
              additional: false,
              total_kg: 1500,
              by_emission_type: {},
            },
          },
          per_fte: {},
          // Non-empty so HomePage's ``hasValidatedData`` renders the chart
          // instead of the empty "ready to start" state.
          validated_buckets: [
            'process_emissions',
            'equipment',
            'external_cloud_and_ai',
            'professional_travel',
          ],
          total_fte: 0,
          total_tonnes_validated_co2eq: 6.5,
        },
      }),
    });
  });
}
