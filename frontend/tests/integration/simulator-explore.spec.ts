/**
 * Integration tests for SimulationExplorePage — verifies that the two
 * reactive-update bugs are fixed WITHOUT a page reload:
 *
 *   Bug 1: submodule count "(x)" next to the submodule name stays stale after
 *          adding an entry.  Fixed in modules.ts getModuleTotals() by keeping
 *          state.moduleTotalsMap in sync after each fetch.
 *
 *   Bug 2: emission breakdown chart / total CO₂eq doesn't update after adding
 *          an entry.  Fixed in ModuleCarbonFootprintChart.vue by adding
 *          :update-options="{ replaceMerge: ['dataset'] }" so ECharts replaces
 *          the stale dataset instead of merging it.
 *
 * The suite mocks the HTTP boundary (page.route) so the guards run normally
 * (unit, year, and selectedCarbonReport are all populated before onMounted
 * fires) without needing a real backend.  __LIGHTHOUSE_BYPASS__ is NOT used
 * because it skips validateUnitGuard entirely, leaving selectedUnit null and
 * causing a TypeError in SimulationExplorePage onMounted.
 *
 * i18n strings (EN):
 *   headcount-member-table-title  → "Member ({count})| Members ({count})"
 *   count=0 → "Members (0)"   (plural)
 *   count=1 → "Member (1)"    (singular)
 *
 *   formatTonnesCO2(0) → "0.0"   (|value| < 1 → 1 decimal)
 *   formatTonnesCO2(5) → "5"     (|value| ≥ 1 → 0 decimals)
 */
import { test, expect } from '@playwright/test';
import { mockSimulatorBackend, SIMULATOR_URL } from './setup/simulator-mocks';

test.describe('simulation explore — reactive updates after adding entry', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any persisted Pinia state (e.g. selectedParams) that could bleed
    // between tests and cause validateUnitGuard to navigate elsewhere.
    await page.addInitScript(() => {
      try {
        localStorage.clear();
      } catch {
        // Ignore — some contexts restrict localStorage before first load.
      }
    });
  });

  test('submodule count updates reactively after posting entry', async ({
    page,
  }) => {
    await mockSimulatorBackend(page);
    await page.goto(SIMULATOR_URL);

    // Wait for simulatorReady (set after selectSimulatorExploreCarbonReport).
    await expect(page.locator('.q-list')).toBeVisible();

    // Expand the Headcount module section.
    await page.getByText('Headcount', { exact: true }).first().click();

    // Member submodule header shows "(0)" on initial load.
    await expect(page.getByText('Members (0)')).toBeVisible();

    // Expand the member submodule to reveal the form.
    await page.getByText('Members (0)').click();

    // Wait for the Add button to confirm the form rendered.
    await expect(
      page.getByRole('button', { name: 'Add', exact: true }),
    ).toBeVisible();

    // Fill the Name field so we're submitting realistic data.
    await page.locator('input[type="text"]').first().fill('Test Member');

    // Submit the entry.
    await page.getByRole('button', { name: 'Add', exact: true }).click();

    // Bug 1 regression guard: the count must update to 1 WITHOUT a page
    // reload.  Playwright's toBeVisible times out if the element never
    // appears, which would indicate the bug is still present.
    await expect(page.getByText('Member (1)')).toBeVisible();
  });

  test('total CO₂eq updates reactively after posting entry', async ({
    page,
  }) => {
    await mockSimulatorBackend(page);
    await page.goto(SIMULATOR_URL);

    // Wait for the module list and for the BigNumber value to stabilise.
    await expect(page.locator('.q-list')).toBeVisible();

    // Initial total is 0 → formatTonnesCO2(0) = "0.0".
    await expect(page.locator('.big-number__value')).toContainText('0.0');

    // Expand Headcount module then member submodule.
    await page.getByText('Headcount', { exact: true }).first().click();
    await expect(page.getByText('Members (0)')).toBeVisible();
    await page.getByText('Members (0)').click();
    await expect(
      page.getByRole('button', { name: 'Add', exact: true }),
    ).toBeVisible();

    // Submit an entry.
    await page.getByRole('button', { name: 'Add', exact: true }).click();

    // Bug 2 regression guard: the breakdown total must update to 5 WITHOUT a
    // page reload.  formatTonnesCO2(5) = "5".
    await expect(page.locator('.big-number__value')).toContainText('5');
  });
});
