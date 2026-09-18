/**
 * #2749 — the equipment "Planning mode" toggle (manual per line vs global
 * percentage, #1981) is offered in the Detailed per Year sections, not only
 * in the Project Grant section, and the mode follows the backend: the
 * prefill starts equipment in global mode at 0%.
 *
 * The section is mounted with its Equipment module expanded; every API call
 * behind it is answered with an empty page so only the mode block matters.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import PlannerYearSection from '@/components/organisms/planner/PlannerYearSection.vue';

const EQUIPMENT_MODULE_TYPE_ID = 4;

function yearData(
  isGrant: boolean,
  equipmentStats: Record<string, number> | null = null,
) {
  return {
    id: 7,
    year: 2027,
    reference_year: 2025,
    is_grant: isGrant,
    budget: null,
    budget_currency: null,
    stats: null,
    factor_year: 2025,
    modules: [
      {
        id: 70,
        carbon_report_id: 7,
        module_type_id: EQUIPMENT_MODULE_TYPE_ID,
        status: 0,
        is_active: true,
        budgets: null,
        stats: equipmentStats,
      },
    ],
  };
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, totals: {} }),
    }),
  );
});

test('a Detailed per Year section offers the equipment planning mode toggle', async ({
  mount,
}) => {
  const component = await mount(PlannerYearSection, {
    props: {
      planId: 1,
      yearData: yearData(false),
      unitId: 3,
      referenceYearOptions: [],
      expandedKeys: ['2027-equipment'],
      projectYearsCount: null,
    },
  });

  const labels = component.locator('button.planner-mode__label');
  await expect(labels).toHaveCount(2);
  // Per-line is the default, exactly as in the grant section.
  await expect(labels.nth(0)).toHaveAttribute('aria-pressed', 'true');
  await expect(labels.nth(1)).toHaveAttribute('aria-pressed', 'false');
});

test('the grant section keeps the same toggle', async ({ mount }) => {
  const component = await mount(PlannerYearSection, {
    props: {
      planId: 1,
      yearData: yearData(true),
      unitId: 3,
      referenceYearOptions: [],
      expandedKeys: ['grant-equipment'],
      projectYearsCount: 3,
    },
  });

  await expect(component.locator('button.planner-mode__label')).toHaveCount(2);
});

test('a prefilled section opens in global mode', async ({ mount }) => {
  const component = await mount(PlannerYearSection, {
    props: {
      planId: 1,
      yearData: yearData(false, {
        equipment_applied_percentage: 0,
        equipment_reference_total_kg: 1500,
      }),
      unitId: 3,
      referenceYearOptions: [],
      expandedKeys: ['2027-equipment'],
      projectYearsCount: null,
    },
  });

  const labels = component.locator('button.planner-mode__label');
  await expect(labels.nth(0)).toHaveAttribute('aria-pressed', 'false');
  await expect(labels.nth(1)).toHaveAttribute('aria-pressed', 'true');
});

test('a reference-year change re-reads the mode from the rebuilt module', async ({
  mount,
  page,
}) => {
  let rebuilt = false;
  await page.route('**/api/v1/project-plans/1/years/2027', (route) => {
    rebuilt = true;
    return route.fulfill({
      json: { ...yearData(false), reference_year: 2024, prefill_job_id: null },
    });
  });
  await page.route(/\/modules\/equipment\?preview_limit=0/, (route) =>
    route.fulfill({
      json: {
        carbon_report_module_id: 70,
        stats: rebuilt ? { equipment_applied_percentage: 0 } : null,
        items: [],
        totals: {},
      },
    }),
  );
  const component = await mount(PlannerYearSection, {
    props: {
      planId: 1,
      yearData: yearData(false),
      unitId: 3,
      referenceYearOptions: [
        { label: '2025', value: 2025 },
        { label: '2024', value: 2024 },
      ],
      expandedKeys: ['2027-equipment'],
      projectYearsCount: null,
    },
  });
  const labels = component.locator('button.planner-mode__label');
  await expect(labels.nth(0)).toHaveAttribute('aria-pressed', 'true');

  // The year section mounts collapsed; open it by its title (the header's
  // info icon stops the click).
  await component.getByText('2027', { exact: true }).click();
  await component.getByRole('button', { name: 'Change' }).click();
  const dialog = page.locator('.q-dialog');
  await dialog.locator('.q-select').click();
  await page.getByRole('option', { name: '2024' }).click();
  await dialog.getByRole('checkbox').click();
  await dialog.getByRole('button', { name: 'Validate' }).click();

  await expect(labels.nth(1)).toHaveAttribute('aria-pressed', 'true');
});
