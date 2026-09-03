/**
 * Regression test for #2401 — every taxonomy request carries the active
 * locale, single-entry path included.
 *
 * The bug: `moduleStore.getSubmoduleTaxonomy` (the path ModuleTable uses
 * when one submodule expands) hand-built its URL inside the store with
 * only `?year=`, so the backend never saw `lang` and served English
 * labels regardless of locale — while the batch path, going through
 * `api/taxonomies.ts`, sent it correctly. The store now routes through
 * `getDataEntryTaxonomy`, which derives `lang` from the i18n locale
 * (`'fr-CH'` → `'fr'`).
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import TaxonomyLangHarness from './fixtures/TaxonomyLangHarness.vue';

test('single-entry taxonomy request carries lang from the active locale', async ({
  mount,
  page,
}) => {
  const requested: URL[] = [];

  await page.route('**/api/v1/taxonomies/**', (route) => {
    requested.push(new URL(route.request().url()));
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ name: 'it', label: 'Informatique' }),
    });
  });

  const component = await mount(TaxonomyLangHarness, {
    props: {
      moduleType: 'equipment',
      submoduleType: 'it',
      year: '2026',
      locale: 'fr-CH',
    },
  });

  await expect.poll(() => requested.length).toBe(1);
  const url = requested[0];
  expect(url.pathname).toBe('/api/v1/taxonomies/module/equipment/it');
  expect(url.searchParams.get('year')).toBe('2026');
  expect(url.searchParams.get('lang')).toBe('fr');

  await expect(component.getByTestId('taxonomy')).toHaveText('resolved');
});
