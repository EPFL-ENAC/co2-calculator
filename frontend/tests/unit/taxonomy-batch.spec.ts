/**
 * Regression test for #2049 T6 — the report page's fan-out over
 * `GET /taxonomies/module/{module}/{data_entry}` (~11 calls, one per
 * submodule) collapses into one `GET .../data-entries` call per module.
 *
 * `moduleStore.getSubmoduleTaxonomiesBatch` is the store action
 * `useSimulationExplorePrintData` now calls once per module instead of
 * calling `getSubmoduleTaxonomy` once per submodule — this pins that a
 * module with several submodules needing a taxonomy fires exactly one
 * HTTP request, not one per submodule.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import TaxonomyBatchHarness from './fixtures/TaxonomyBatchHarness.vue';

test('one batched request replaces one-per-submodule taxonomy calls', async ({
  mount,
  page,
}) => {
  const requestedPaths: string[] = [];

  await page.route('**/api/v1/taxonomies/**', (route) => {
    const url = new URL(route.request().url());
    requestedPaths.push(url.pathname);

    if (url.pathname.endsWith('/data-entries')) {
      expect(url.searchParams.getAll('entries')).toEqual([
        'scientific',
        'it',
        'other',
      ]);
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scientific: { name: 'scientific', label: 'Scientific' },
          it: { name: 'it', label: 'IT' },
          other: { name: 'other', label: 'Other' },
        }),
      });
    }
    // Any single-entry call landing here would mean the old N-calls
    // behavior regressed back in — fail loudly instead of fulfilling it.
    throw new Error(`unexpected single-entry taxonomy request: ${url}`);
  });

  await mount(TaxonomyBatchHarness, {
    props: {
      moduleType: 'equipment',
      entries: ['scientific', 'it', 'other'],
      year: '2025',
    },
  });

  await expect.poll(() => requestedPaths.length).toBe(1);
  expect(requestedPaths[0]).toBe(
    '/api/v1/taxonomies/module/equipment/data-entries',
  );
});

/**
 * #2258 follow-up — the backend omits an entry it couldn't resolve
 * instead of failing the whole batch (logged loud server-side). That
 * must not read as a silent success on the frontend: the other entries
 * still resolve, but the gap surfaces through the store's error state.
 */
test('a submodule missing from the batch response surfaces a visible error', async ({
  mount,
  page,
}) => {
  await page.route('**/api/v1/taxonomies/**', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        scientific: { name: 'scientific', label: 'Scientific' },
        // "it" omitted -- simulates a per-entry runtime failure.
        other: { name: 'other', label: 'Other' },
      }),
    });
  });

  const component = await mount(TaxonomyBatchHarness, {
    props: {
      moduleType: 'equipment',
      entries: ['scientific', 'it', 'other'],
      year: '2025',
    },
  });

  await expect(component.getByTestId('taxonomy-scientific')).toHaveText(
    'resolved',
  );
  await expect(component.getByTestId('taxonomy-it')).toHaveText('missing');
  await expect(component.getByTestId('taxonomy-other')).toHaveText('resolved');
  await expect(component.getByTestId('store-error')).toHaveText(/it/);
});
