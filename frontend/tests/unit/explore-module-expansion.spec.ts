/**
 * Regression test for the explore-page mount stampede (#2360, GlitchTip 312):
 * `SimulationExplorePage` rendered one collapsed `q-expansion-item` per
 * module, but QExpansionItem mounts its default slot even while collapsed —
 * so a single page load fired every module's `preview_limit=0` count fetch,
 * every submodule form's option lookup, and `PlannerResearchFacilityRows`'s
 * own lookup (the exact GlitchTip call) all at once. Both lookups are the
 * taxonomy endpoint since #2391 decision 1.
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
// One endpoint now backs both lookups, so they are told apart by module
// segment: research-facilities is the planner grid's, anything else a form's.
const TAXONOMY_URL = '**/api/v1/taxonomies/module/**';
const RF_ENTRIES_URL =
  '**/api/v1/carbon-reports/*/modules/research-facilities/*';

async function routeCounters(page: Page) {
  const counts = {
    preview: [] as string[],
    formTaxonomy: 0,
    rfTaxonomy: [] as string[],
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
  await page.route(TAXONOMY_URL, async (route) => {
    const url = route.request().url();
    if (url.includes('/module/research-facilities/')) {
      counts.rfTaxonomy.push(url);
    } else {
      counts.formTaxonomy++;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ name: 'root', label: 'root', children: [] }),
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

test('mounting the module list fires zero count and zero taxonomy lookup requests', async ({
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
  expect(counts.formTaxonomy).toBe(0);
  expect(counts.rfTaxonomy).toHaveLength(0);
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

test('opening ResearchFacilities fetches its taxonomy once, content stays mounted on re-collapse', async ({
  page,
  mount,
}) => {
  const counts = await routeCounters(page);

  const component = await mount(ExploreModuleExpansionHarness);

  await component.getByTestId(RESEARCH_FACILITIES_TITLE_TESTID).click();

  await expect.poll(() => counts.rfTaxonomy.length).toBeGreaterThan(0);

  // ResearchFacilities has no submodule-count prefetch (task #2360 spec).
  expect(counts.preview).toHaveLength(0);

  const rfLookupsAfterFirstOpen = counts.rfTaxonomy.length;

  // Collapse and reopen: PlannerResearchFacilityRows stays mounted, its own
  // onMounted never runs a second time.
  await component.getByTestId(RESEARCH_FACILITIES_TITLE_TESTID).click();
  await component.getByTestId(RESEARCH_FACILITIES_TITLE_TESTID).click();
  await page.waitForTimeout(200);

  expect(counts.rfTaxonomy.length).toBe(rfLookupsAfterFirstOpen);
});
