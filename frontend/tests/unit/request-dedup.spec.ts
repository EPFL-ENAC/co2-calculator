/**
 * Regression tests for the explore-page request stampede (#2360).
 *
 * `resolveCarbonReportId` cached the resolved id only AFTER the await, so N
 * concurrent callers (every module table/chart/select mounting at once) each
 * fired their own identical lookup — 11 observed on one explore-page load.
 * Same pattern for `getHeadcountMembers` (4 observed). Both now share one
 * in-flight promise per key; rejections are never cached.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import RequestDedupHarness from './RequestDedupHarness.vue';

const REPORT_LOOKUP_URL = '**/api/v1/carbon-reports/unit/7/year/2024/';
const MEMBERS_URL = '**/api/v1/carbon-reports/9/modules/headcount/members';
const EXPLORE_LOOKUP_URL =
  '**/api/v1/carbon-reports/simulator/explore/unit/7/reference-year/2024/';

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
