/**
 * #3218 — a 503 `database_unavailable` is an outage, not a bug.
 *
 * Before the fix the client showed the raw backend code as a red toast
 * (and reported it to GlitchTip like any 5xx). It must show the translated
 * "service unavailable, not saved, try again" notice instead, and still
 * reject, so the calling form keeps the user's input.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import SlowFactorsHarness from './fixtures/SlowFactorsHarness.vue';

test('a database outage shows the unavailable notice, not the raw code', async ({
  mount,
  page,
}) => {
  await page.route(
    '**/api/v1/taxonomies/module/equipment/scientific**',
    (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        headers: { 'Retry-After': '30' },
        body: JSON.stringify({ detail: 'database_unavailable' }),
      }),
  );

  const component = await mount(SlowFactorsHarness, {
    props: { moduleType: 'equipment', dataEntry: 'scientific', year: '2025' },
  });

  await expect(component.getByTestId('outcome')).toHaveText('aborted');
  await expect(component.getByTestId('error-name')).toHaveText('HTTPError');
  await expect(
    page.getByText(/temporarily unavailable|momentanément indisponible/),
  ).toBeVisible();
  await expect(
    page.getByText('database_unavailable', { exact: true }),
  ).toHaveCount(0);
});
