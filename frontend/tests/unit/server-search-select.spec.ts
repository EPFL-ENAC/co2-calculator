/**
 * #2391 decision 4 — the purchase classification select searches the
 * server per keystroke instead of downloading the ~17k-node taxonomy.
 * Pins the request shape (`query`/`year`/`lang` on the options endpoint),
 * the emitted value being the code (not the label), and the min-2-chars
 * guard that keeps requests the backend would 422 from ever firing.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import ServerSearchSelectHarness from './fixtures/ServerSearchSelectHarness.vue';

const HARNESS_PROPS = {
  moduleType: 'purchase',
  submoduleType: 'other_purchases',
  year: 2026,
};

test('searches the server per keystroke and emits the picked code', async ({
  mount,
  page,
}) => {
  const requested: URL[] = [];
  await page.route('**/api/v1/taxonomies/**', (route) => {
    requested.push(new URL(route.request().url()));
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { name: '27112700', label: 'Outils électriques' },
        { name: '43211501', label: 'Serveurs informatiques' },
      ]),
    });
  });

  const component = await mount(ServerSearchSelectHarness, {
    props: HARNESS_PROPS,
  });

  await component.locator('input').fill('outils');

  await expect.poll(() => requested.length).toBe(1);
  const url = requested[0];
  expect(url.pathname).toBe(
    '/api/v1/taxonomies/module/purchase/other_purchases/options',
  );
  expect(url.searchParams.get('query')).toBe('outils');
  expect(url.searchParams.get('year')).toBe('2026');
  expect(url.searchParams.get('lang')).toBe('en');

  await page.getByRole('option', { name: 'Outils électriques' }).click();
  await expect(component.getByTestId('selected')).toHaveText('27112700');
});

test('French locale sends lang=fr on the options request', async ({
  mount,
  page,
}) => {
  const requested: URL[] = [];
  await page.route('**/api/v1/taxonomies/**', (route) => {
    requested.push(new URL(route.request().url()));
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ name: '27112700', label: 'Outils électriques' }]),
    });
  });

  const component = await mount(ServerSearchSelectHarness, {
    props: { ...HARNESS_PROPS, locale: 'fr-CH' },
  });

  await component.locator('input').fill('outils');

  await expect.poll(() => requested.length).toBe(1);
  expect(requested[0].searchParams.get('lang')).toBe('fr');
});

test('edit mode shows the row label with zero requests', async ({
  mount,
  page,
}) => {
  let requests = 0;
  await page.route('**/api/v1/**', (route) => {
    requests += 1;
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '[]',
    });
  });

  const component = await mount(ServerSearchSelectHarness, {
    props: {
      ...HARNESS_PROPS,
      initialValue: '27112700',
      initialOption: { value: '27112700', label: 'Outils électriques' },
    },
  });

  // `map-options` resolves the label from the seeded option — no fetch.
  await expect(component.locator('input')).toHaveValue('Outils électriques');
  expect(requests).toBe(0);
});

test('a failed lookup surfaces an error instead of a silent blank', async ({
  mount,
  page,
}) => {
  await page.route('**/api/v1/taxonomies/**', (route) =>
    route.fulfill({ status: 500, body: 'boom' }),
  );

  const component = await mount(ServerSearchSelectHarness, {
    props: HARNESS_PROPS,
  });

  await component.locator('input').fill('outils');

  await expect(
    component.getByText('Options could not be loaded. Try again later.'),
  ).toBeVisible();
});

test('input below 2 characters never hits the server', async ({
  mount,
  page,
}) => {
  let requests = 0;
  await page.route('**/api/v1/taxonomies/**', (route) => {
    requests += 1;
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '[]',
    });
  });

  const component = await mount(ServerSearchSelectHarness, {
    props: HARNESS_PROPS,
  });

  await component.locator('input').fill('o');
  // Outwait the 300ms input debounce before asserting nothing fired.
  await page.waitForTimeout(600);
  expect(requests).toBe(0);
});
