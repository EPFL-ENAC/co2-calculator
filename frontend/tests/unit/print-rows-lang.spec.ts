/**
 * Regression test for #2160 — the print page's row requests carry the
 * active locale. Purchase rows are printed from their backend-resolved
 * `labels` (no taxonomy tree), and the rows endpoint defaults to English,
 * so without `lang` a French report printed English descriptions.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import PrintRowsLangHarness from './fixtures/PrintRowsLangHarness.vue';

test('print row requests carry lang from the active locale', async ({
  mount,
  page,
}) => {
  const requested: URL[] = [];

  await page.route('**/api/v1/carbon-reports/**', (route) => {
    requested.push(new URL(route.request().url()));
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{ id: 1, labels: { name: 'Ordinateurs' } }],
        summary: { total_items: 1 },
      }),
    });
  });

  const component = await mount(PrintRowsLangHarness, {
    props: {
      moduleType: 'purchase',
      submoduleId: 'it_equipment',
      carbonReportId: 7,
      locale: 'fr-CH',
    },
  });

  await expect(component.getByTestId('rows')).toHaveText('1');
  expect(requested).toHaveLength(1);
  expect(requested[0]?.pathname).toBe(
    '/api/v1/carbon-reports/7/modules/purchase/it_equipment',
  );
  expect(requested[0]?.searchParams.get('lang')).toBe('fr');
});
