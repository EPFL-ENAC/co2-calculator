/**
 * #3153 — the pipeline console's recalculate-emissions card posts to the
 * per-type endpoint when a data entry type is picked, and to the module
 * endpoint with only_stale=false when it is left empty.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import type { Page } from 'playwright/test';
import RecalculateEmissionsCard from '@/components/molecules/backoffice/RecalculateEmissionsCard.vue';

async function mockApi(page: Page): Promise<string[]> {
  const posts: string[] = [];
  await page.route(
    (url) => url.pathname.endsWith('/year-configuration/'),
    (route) =>
      route.fulfill({
        json: [{ year: 2024, is_started: true, updated_at: '2024-01-01' }],
      }),
  );
  await page.route('**/sync/recalculate-emissions/**', (route) => {
    const url = new URL(route.request().url());
    posts.push(url.pathname.split('/sync/')[1] + url.search);
    return route.fulfill({ json: { job_id: 1 } });
  });
  return posts;
}

async function pick(page: Page, testId: string, option: string) {
  await page.getByTestId(testId).click();
  await page.getByRole('option', { name: option, exact: true }).click();
}

test('module + type + year posts to the per-type endpoint', async ({
  mount,
  page,
}) => {
  const posts = await mockApi(page);
  let triggered = 0;
  await mount(RecalculateEmissionsCard, {
    on: { triggered: () => triggered++ },
  });

  await pick(page, 'recalc-module', 'Professional travel');
  await pick(page, 'recalc-type', 'train');
  await pick(page, 'recalc-year', '2024');
  await page.getByTestId('recalc-trigger').click();

  await expect(page.locator('.q-dialog')).toContainText(
    'This will overwrite all previous carbon reports',
  );
  await page.getByTestId('recalc-confirm').click();

  await expect.poll(() => triggered).toBe(1);
  expect(posts).toEqual(['recalculate-emissions/2/21?year=2024']);
});

test('module + year only posts a full module recalc', async ({
  mount,
  page,
}) => {
  const posts = await mockApi(page);
  await mount(RecalculateEmissionsCard);

  await pick(page, 'recalc-module', 'Professional travel');
  await pick(page, 'recalc-year', '2024');
  await page.getByTestId('recalc-trigger').click();
  await page.getByTestId('recalc-confirm').click();

  await expect
    .poll(() => posts)
    .toEqual(['recalculate-emissions/2?year=2024&only_stale=false']);
});
