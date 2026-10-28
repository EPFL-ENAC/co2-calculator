/**
 * #939 — the travel from/to search pages through the server's ranked
 * results: once the last option of a full page renders, the next page is
 * requested and appended; a short page ends the paging. Before the fix the
 * client never sent `page` (and the backend ignored it), so the list
 * stopped at the first 20 matches.
 */
import { test, expect } from '@playwright/experimental-ct-vue';
import CO2DestinationInput from '@/components/atoms/CO2DestinationInput.vue';

const PAGE_SIZE = 20;

function stations(page: number, count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: page * 100 + i,
    name: `Station p${page}-${i}`,
    latitude: 46.9,
    longitude: 7.4,
    country_code: 'CH',
    natural_key: `train:ch:p${page}-${i}`,
    transport_mode: 'train',
  }));
}

test('scrolling to the last option loads the next page until a short one', async ({
  mount,
  page,
}) => {
  const requested: URL[] = [];
  await page.route('**/api/v1/locations/search**', (route) => {
    const url = new URL(route.request().url());
    requested.push(url);
    const n = Number(url.searchParams.get('page'));
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(stations(n, n === 1 ? PAGE_SIZE : 5)),
    });
  });

  const component = await mount(CO2DestinationInput, {
    props: { transportMode: 'train' },
  });
  await component.locator('input').first().fill('be');

  await page
    .getByRole('option', { name: 'Station p1-19' })
    .scrollIntoViewIfNeeded();
  await page
    .getByRole('option', { name: 'Station p2-4' })
    .scrollIntoViewIfNeeded();

  const pageTwo = requested[1];
  expect(pageTwo.searchParams.get('query')).toBe('be');
  expect(pageTwo.searchParams.get('transport_mode')).toBe('train');
  expect(pageTwo.searchParams.get('limit')).toBe(String(PAGE_SIZE));

  // A negative assertion needs a window: give a wrongly-fired page 3 time
  // to show up after the short page 2 reached the bottom.
  await page.waitForTimeout(300);
  expect(requested.map((u) => u.searchParams.get('page'))).toEqual(['1', '2']);
});
