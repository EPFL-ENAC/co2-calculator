/**
 * #2401 live-testing bug — with a submodule table open, switching the
 * navbar language never refetched it, so rows kept the previous locale's
 * labels (and the search filter kept matching the old language) until a
 * re-expand. The module store now records each submodule's last fetch
 * args and replays every *loaded* submodule when the i18n locale changes.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import LocaleRefetchHarness from './fixtures/LocaleRefetchHarness.vue';

const SUBMODULE_RESPONSE = {
  id: 66,
  count: 0,
  items: [],
  summary: {
    total_items: 0,
    annual_fte: 0,
    annual_consumption_kwh: 0,
    total_kg_co2eq: 0,
  },
  has_more: false,
};

test('a locale switch refetches the open submodule with the new lang', async ({
  mount,
  page,
}) => {
  const requested: URL[] = [];
  await page.route('**/api/v1/carbon-reports/**', (route) => {
    requested.push(new URL(route.request().url()));
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(SUBMODULE_RESPONSE),
    });
  });

  const component = await mount(LocaleRefetchHarness, {
    props: { locale: 'en-US' },
  });

  await expect.poll(() => requested.length).toBe(1);
  expect(requested[0].searchParams.get('lang')).toBe('en');
  // Page-level lookup: the async store write re-patches the harness root,
  // which the CT component handle does not always track.
  await expect(page.getByTestId('loaded')).toHaveText('yes');

  await component.update({ props: { locale: 'fr-CH' } });

  await expect.poll(() => requested.length).toBe(2);
  expect(requested[1].searchParams.get('lang')).toBe('fr');
  expect(requested[1].pathname).toBe(requested[0].pathname);
});
