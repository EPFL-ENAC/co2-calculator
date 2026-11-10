/**
 * #2787 — the "Open year for users" button is greyed out while a module is
 * incomplete, and the page names the modules that block it (the same ones
 * the backend PATCH answers 409 for).
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import OpenYearButtonHarness from './fixtures/OpenYearButtonHarness.vue';
import type { YearConfigurationResponse } from '@/stores/yearConfig';

const COMPLETE_REDUCTION_OBJECTIVES = {
  goals: [
    { target_year: 2030, reference_year: 2019, reduction_percentage: 0.5 },
  ],
  files: {
    institutional_footprint: { path: 'a.csv' },
    population_projections: { path: 'b.csv' },
    unit_scenarios: { path: 'c.csv' },
  },
};

// Backend keys modules by ModuleTypeEnum id: 1 = headcount, 2 = travel.
function response(headcountIncomplete: boolean): YearConfigurationResponse {
  return {
    year: 2024,
    is_started: false,
    configuration_completed: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    min_configurable_year: 2020,
    recalculation_status: [],
    config: {
      modules: {
        '1': { enabled: true, incomplete: headcountIncomplete, submodules: {} },
        '2': { enabled: true, incomplete: false, submodules: {} },
      },
      reduction_objectives: COMPLETE_REDUCTION_OBJECTIVES,
    },
  } as unknown as YearConfigurationResponse;
}

test('incomplete module disables the button and is listed', async ({
  mount,
  page,
}) => {
  await mount(OpenYearButtonHarness, { props: { response: response(true) } });

  await expect(page.getByTestId('open-year-for-users-btn')).toBeDisabled();
  const list = page.getByTestId('open-year-incomplete-modules');
  await expect(list).toContainText('Headcount');
  await expect(list).not.toContainText('Professional travel');
});

test('complete year enables the button and lists nothing', async ({
  mount,
  page,
}) => {
  await mount(OpenYearButtonHarness, { props: { response: response(false) } });

  await expect(page.getByTestId('open-year-for-users-btn')).toBeEnabled();
  await expect(page.getByTestId('open-year-incomplete-modules')).toHaveCount(0);
});
