/**
 * Regression tests for the explore-page request stampede (#2360).
 *
 * `resolveCarbonReportId` cached the resolved id only AFTER the await, so N
 * concurrent callers (every module table/chart/select mounting at once) each
 * fired their own identical lookup — 11 observed on one explore-page load.
 * Same pattern for `getHeadcountMembers` (4 observed), and for the factors
 * store's `ensureSubclassOptionMap`/`ensureFactorList` (latent — only one
 * form per submodule mounts today, but the same write-after-await gap).
 * All now share one in-flight promise per key; rejections are never cached.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import RequestDedupHarness from './RequestDedupHarness.vue';

const REPORT_LOOKUP_URL = '**/api/v1/carbon-reports/unit/7/year/2024/';
const MEMBERS_URL = '**/api/v1/carbon-reports/9/modules/headcount/members';
const EXPLORE_LOOKUP_URL =
  '**/api/v1/carbon-reports/simulator/explore/unit/7/reference-year/2024/';
// `plane` -> enumSubmodule.plane = 20
const SUBCLASS_MAP_URL = '**/api/v1/factors/20/class-subclass-map*';
const FACTOR_LIST_URL = '**/api/v1/factors/20/list*';
// `research-facilities` -> enumSubmodule['research-facilities'] = 70, the
// endpoint PlannerResearchFacilityRows fires twice on mount (#2391 / GlitchTip 312).
const RF_FACTOR_LIST_URL = '**/api/v1/factors/70/list*';

test('concurrent resolveCarbonReportId calls share one lookup request', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(REPORT_LOOKUP_URL, async (route) => {
    requests++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 123 }),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'resolve-concurrent' },
  });

  await expect(component).toContainText('ids:123,123,123,123,123');
  expect(requests).toBe(1);
});

test('a failed report-id lookup is not cached and retries', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(REPORT_LOOKUP_URL, async (route) => {
    requests++;
    if (requests === 1) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'not found' }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 456 }),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'resolve-retry' },
  });

  await expect(component).toContainText('retried:456');
  expect(requests).toBe(2);
});

test('concurrent getHeadcountMembers calls share one request, later calls refetch', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(MEMBERS_URL, async (route) => {
    requests++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ institutional_id: '100001', name: 'M1' }]),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'members-dedup' },
  });

  // Burst of 3 shares one request; the follow-up call refetches (results are
  // deliberately not cached so roster edits stay visible) — 2 requests total.
  await expect(component).toContainText('members:1,1,1;followup:1');
  expect(requests).toBe(2);
});

test('resolveCarbonReportId reuses the id the workspace store already resolved', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(EXPLORE_LOOKUP_URL, async (route) => {
    requests++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 789, unit_id: 7, year: 2024 }),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'explore-seed-cache' },
  });

  await expect(component).toContainText('seeded:789,resolved:789');
  // Without the seeding fix, resolveCarbonReportId re-issues this same
  // lookup, so 2 requests would land instead of 1 (#2360 follow-up).
  expect(requests).toBe(1);
});

test('concurrent ensureSubclassOptionMap calls share one lookup request', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(SUBCLASS_MAP_URL, async (route) => {
    requests++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ Boeing: ['737', '777'] }),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'subclass-map-concurrent' },
  });

  await expect(component).toContainText('classes:1,1,1,1,1');
  expect(requests).toBe(1);
});

test('a failed subclass-map lookup is not cached and retries', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(SUBCLASS_MAP_URL, async (route) => {
    requests++;
    if (requests === 1) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'not found' }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ Boeing: ['737'] }),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'subclass-map-retry' },
  });

  await expect(component).toContainText('retried:1');
  expect(requests).toBe(2);
});

test('concurrent ensureFactorList calls (via fetchClassOptions labels) share one request', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(FACTOR_LIST_URL, async (route) => {
    requests++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: '1', name: 'Platform One' }]),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'factor-list-concurrent' },
  });

  await expect(component).toContainText('options:1,1,1,1,1');
  expect(requests).toBe(1);
});

test('concurrent fetchFactorList calls (planner lookups) share one request', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(RF_FACTOR_LIST_URL, async (route) => {
    requests++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          researchfacility_id: 1,
          researchfacility_name: 'Platform One',
          use_unit: 'h',
        },
      ]),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'factor-list-direct-concurrent' },
  });

  await expect(component).toContainText('rows:1,1,1,1,1');
  expect(requests).toBe(1);
});
