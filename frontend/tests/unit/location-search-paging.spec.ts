/**
 * #939 — the travel from/to search pages through the server's ranked
 * results: once the last option of a full page renders, the next page is
 * requested and appended; a short page ends the paging. Before the fix the
 * client never sent `page` (and the backend ignored it), so the list
 * stopped at the first 20 matches.
 *
 * The menu also says why it is empty or short (too-short query, no match,
 * failed request) instead of closing on a blank.
 */
import { test, expect } from '@playwright/experimental-ct-vue';
import CO2DestinationInput from '@/components/atoms/CO2DestinationInput.vue';

const PAGE_SIZE = 20;
const LOAD_ERROR = 'Options could not be loaded. Try again later.';

const json = (body: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

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

test('the menu says why it is empty: too short, or no match', async ({
  mount,
  page,
}) => {
  const queries: (string | null)[] = [];
  await page.route('**/api/v1/locations/search**', (route) => {
    queries.push(new URL(route.request().url()).searchParams.get('query'));
    return route.fulfill(json([]));
  });

  const component = await mount(CO2DestinationInput, {
    props: { transportMode: 'train' },
  });
  const input = component.locator('input').first();
  const menu = page.locator('.q-menu');

  // One letter and a space: the backend trims it and rejects it, so no
  // request goes out and the menu asks for more.
  await input.fill('a ');
  await expect(menu).toHaveText('Type at least 2 characters to search');
  await input.fill('zzzzzz');
  await expect(menu).toHaveText('No matching options');
  expect(queries).toEqual(['zzzzzz']);
});

test('a failed search says so instead of looking like no match', async ({
  mount,
  page,
}) => {
  await page.route('**/api/v1/locations/search**', (route) =>
    route.fulfill(json({}, 500)),
  );

  const component = await mount(CO2DestinationInput, {
    props: { transportMode: 'train' },
  });
  await component.locator('input').first().fill('be');

  await expect(page.locator('.q-menu')).toHaveText(LOAD_ERROR);
});

test('a failed next page keeps the rows and says the list stops short', async ({
  mount,
  page,
}) => {
  await page.route('**/api/v1/locations/search**', (route) => {
    const n = Number(new URL(route.request().url()).searchParams.get('page'));
    return route.fulfill(
      n === 1 ? json(stations(1, PAGE_SIZE)) : json({}, 500),
    );
  });

  const component = await mount(CO2DestinationInput, {
    props: { transportMode: 'train' },
  });
  await component.locator('input').first().fill('be');
  await page
    .getByRole('option', { name: 'Station p1-19' })
    .scrollIntoViewIfNeeded();

  await expect(page.locator('.q-menu').getByText(LOAD_ERROR)).toBeVisible();
  await expect(
    page.getByRole('option', { name: 'Station p1-19' }),
  ).toBeVisible();
});

test("a late failure of the previous query's page does not flag the new list", async ({
  mount,
  page,
}) => {
  let failPageTwo = () => {};
  const pageTwoFails = new Promise<void>((resolve) => {
    failPageTwo = resolve;
  });
  let answerBern = () => {};
  const bernAnswered = new Promise<void>((resolve) => {
    answerBern = resolve;
  });
  await page.route('**/api/v1/locations/search**', async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get('query') === 'bern') {
      await bernAnswered;
      return route.fulfill(json(stations(9, 3)));
    }
    if (url.searchParams.get('page') === '2') {
      await pageTwoFails;
      return route.fulfill(json({}, 500));
    }
    return route.fulfill(json(stations(1, PAGE_SIZE)));
  });

  const component = await mount(CO2DestinationInput, {
    props: { transportMode: 'train' },
  });
  const input = component.locator('input').first();
  await input.fill('be');
  const pageTwo = page.waitForRequest((r) => r.url().includes('page=2'));
  await page
    .getByRole('option', { name: 'Station p1-19' })
    .scrollIntoViewIfNeeded();
  await pageTwo;

  // The old query's page 2 fails while the new search is still in flight.
  const bern = page.waitForRequest((r) => r.url().includes('query=bern'));
  await input.fill('bern');
  await bern;
  const pageTwoFailed = page.waitForResponse((r) => r.url().includes('page=2'));
  failPageTwo();
  await pageTwoFailed;
  answerBern();

  await expect(
    page.getByRole('option', { name: 'Station p9-0' }),
  ).toBeVisible();
  await expect(page.locator('.q-menu').getByText(LOAD_ERROR)).toHaveCount(0);
});
