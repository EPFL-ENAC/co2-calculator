/**
 * Regression test for the explore-page mount stampede (#2360, GlitchTip 312):
 * `SimulationExplorePage` rendered one collapsed `q-expansion-item` per
 * module, but QExpansionItem mounts its default slot even while collapsed —
 * so a single page load fired every module's `preview_limit=0` count fetch,
 * every submodule form's `class-subclass-map` fetch, and
 * `PlannerResearchFacilityRows`'s `factors/{id}/list` fetch (the exact
 * GlitchTip call) all at once.
 *
 * `ExploreModuleExpansionList` now gates that content behind an "opened at
 * least once" flag, and fetches a module's counts only on its first open.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import type { Page } from '@playwright/test';
import ExploreModuleExpansionHarness from './ExploreModuleExpansionHarness.vue';

const EQUIPMENT_TITLE_TESTID = 'explore-module-title-equipment';
const RESEARCH_FACILITIES_TITLE_TESTID =
  'explore-module-title-research-facilities';

const REPORT_LOOKUP_URL = '**/api/v1/carbon-reports/unit/7/year/2024/';
const PREVIEW_URL = '**/api/v1/carbon-reports/*/modules/*preview_limit=0*';
const CLASS_SUBCLASS_URL = '**/api/v1/factors/*/class-subclass-map*';
const RF_FACTORS_LIST_URL = '**/api/v1/factors/*/list*';
const RF_ENTRIES_URL =
  '**/api/v1/carbon-reports/*/modules/research-facilities/*';

async function routeCounters(page: Page) {
  const counts = {
    preview: [] as string[],
    classSubclass: 0,
    rfFactorsList: [] as string[],
  };

  await page.route(REPORT_LOOKUP_URL, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 42 }),
    });
  });
  await page.route(PREVIEW_URL, async (route) => {
    counts.preview.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data_entry_types_total_items: {} }),
    });
  });
  await page.route(CLASS_SUBCLASS_URL, async (route) => {
    counts.classSubclass++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({}),
    });
  });
  await page.route(RF_FACTORS_LIST_URL, async (route) => {
    counts.rfFactorsList.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });
  await page.route(RF_ENTRIES_URL, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    });
  });

  return counts;
}

test('mounting the module list fires zero count, class-subclass-map and research-facility-list requests', async ({
  page,
  mount,
}) => {
  const counts = await routeCounters(page);

  await mount(ExploreModuleExpansionHarness);
  // Give any errant mount-time fetch a moment to actually reach the network
  // layer before asserting its absence (a fire-and-forget call can still be
  // in flight the instant mount() resolves).
  await page.waitForTimeout(300);

  expect(counts.preview).toHaveLength(0);
  expect(counts.classSubclass).toBe(0);
  expect(counts.rfFactorsList).toHaveLength(0);
});

test('opening a module fetches only that module counts, once', async ({
  page,
  mount,
}) => {
  const counts = await routeCounters(page);

  const component = await mount(ExploreModuleExpansionHarness);

  await component.getByTestId(EQUIPMENT_TITLE_TESTID).click();

  await expect.poll(() => counts.preview.length).toBeGreaterThan(0);

  // Only Equipment's own preview_limit=0 fired — never Purchase's.
  expect(
    counts.preview.every((url) => url.includes('/modules/equipment')),
  ).toBe(true);
  expect(counts.preview.some((url) => url.includes('/modules/purchase'))).toBe(
    false,
  );

  const previewAfterFirstOpen = counts.preview.length;

  // Collapse and reopen: content stays mounted, no duplicate count fetch.
  await component.getByTestId(EQUIPMENT_TITLE_TESTID).click();
  await component.getByTestId(EQUIPMENT_TITLE_TESTID).click();

  expect(counts.preview.length).toBe(previewAfterFirstOpen);
});

test('opening ResearchFacilities fetches its factor list once, content stays mounted on re-collapse', async ({
  page,
  mount,
}) => {
  const counts = await routeCounters(page);

  const component = await mount(ExploreModuleExpansionHarness);

  await component.getByTestId(RESEARCH_FACILITIES_TITLE_TESTID).click();

  await expect.poll(() => counts.rfFactorsList.length).toBeGreaterThan(0);

  // ResearchFacilities has no submodule-count prefetch (task #2360 spec).
  expect(counts.preview).toHaveLength(0);

  const rfListAfterFirstOpen = counts.rfFactorsList.length;

  // Collapse and reopen: PlannerResearchFacilityRows stays mounted, its own
  // onMounted never runs a second time.
  await component.getByTestId(RESEARCH_FACILITIES_TITLE_TESTID).click();
  await component.getByTestId(RESEARCH_FACILITIES_TITLE_TESTID).click();
  await page.waitForTimeout(200);

  expect(counts.rfFactorsList.length).toBe(rfListAfterFirstOpen);
});
