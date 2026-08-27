/**
 * Regression tests for the explore-page request stampede (#2360).
 *
 * `resolveCarbonReportId` cached the resolved id only AFTER the await, so N
 * concurrent callers (every module table/chart/select mounting at once) each
 * fired their own identical lookup — 11 observed on one explore-page load.
 * Same pattern for `getHeadcountMembers` (4 observed), and for the factors
 * store's lookup fetch (latent — only one form per submodule mounts today,
 * but the same write-after-await gap).
 * All now share one in-flight promise per key; rejections are never cached.
 *
 * Since #2391 decision 1 that lookup is the taxonomy endpoint: plain options,
 * labelled options and the planner's facility nodes all read one cache entry
 * per (submodule, year), so the dedup covers all three at once.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import RequestDedupHarness from './RequestDedupHarness.vue';

const REPORT_LOOKUP_URL = '**/api/v1/carbon-reports/unit/7/year/2024/';
const MEMBERS_URL = '**/api/v1/carbon-reports/9/modules/headcount/members';
const EXPLORE_LOOKUP_URL =
  '**/api/v1/carbon-reports/simulator/explore/unit/7/reference-year/2024/';
const PLANE_TAXONOMY_URL =
  '**/api/v1/taxonomies/module/professional-travel/plane*';
// The endpoint PlannerResearchFacilityRows fires twice on mount
// (#2391 / GlitchTip 312).
const RF_TAXONOMY_URL =
  '**/api/v1/taxonomies/module/research-facilities/research-facilities*';

const PLANE_TAXONOMY = {
  name: 'plane',
  label: 'Plane',
  children: [
    {
      name: 'Boeing',
      label: 'Boeing',
      children: [
        { name: '777', label: '777' },
        { name: '737', label: '737' },
        // The retired class-subclass-map deduped server-side; the tree
        // doesn't, so the store has to. Deliberately NOT re-sorted (#2412):
        // subclass codes are a plain classification list where the value
        // IS the label, so the backend's declared order can be meaningful
        // and sorting would silently discard it. First-occurrence order is
        // preserved through the dedup: 777, 737 (the second 737 drops).
        { name: '737', label: '737' },
      ],
    },
  ],
};

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

test('concurrent class-option lookups share one taxonomy request', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(PLANE_TAXONOMY_URL, async (route) => {
    requests++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(PLANE_TAXONOMY),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'class-options-concurrent' },
  });

  await expect(component).toContainText('classes:1,1,1,1,1');
  expect(requests).toBe(1);
});

test('a failed taxonomy lookup is not cached and retries', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(PLANE_TAXONOMY_URL, async (route) => {
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
      body: JSON.stringify(PLANE_TAXONOMY),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'class-options-retry' },
  });

  await expect(component).toContainText('retried:1');
  expect(requests).toBe(2);
});

test('concurrent labelled class-option lookups share one request', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(PLANE_TAXONOMY_URL, async (route) => {
    requests++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(PLANE_TAXONOMY),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'labelled-options-concurrent' },
  });

  await expect(component).toContainText('options:1,1,1,1,1');
  expect(requests).toBe(1);
});

test('concurrent fetchClassNodes calls (planner lookups) share one request', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(RF_TAXONOMY_URL, async (route) => {
    requests++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        name: 'research_facilities',
        label: 'Research facilities',
        children: [
          { name: '1902', label: 'Platform One', meta: { use_unit: 'h' } },
        ],
      }),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'class-nodes-concurrent' },
  });

  await expect(component).toContainText('rows:1,1,1,1,1');
  expect(requests).toBe(1);
});

test('subclass options are deduped but not re-sorted, off the same cached tree', async ({
  page,
  mount,
}) => {
  let requests = 0;
  await page.route(PLANE_TAXONOMY_URL, async (route) => {
    requests++;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(PLANE_TAXONOMY),
    });
  });

  const component = await mount(RequestDedupHarness, {
    props: { scenario: 'subclass-options' },
  });

  // Deduped (the second '737' drops), not re-sorted: 777 stays first,
  // matching the backend-declared child order (#2412).
  await expect(component).toContainText('subclasses:777|737');
  expect(requests).toBe(1);
});
