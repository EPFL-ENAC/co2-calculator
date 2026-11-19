/**
 * Regression tests for the session guard (#2983).
 *
 * Finding 2: a 5xx or a network error on GET /session sent a signed-in user
 * to /login until a full reload. Finding 6: only GET /session renews now, so
 * the guard re-asks it once the last check is an hour old. Finding 3: a
 * session check in flight at logout must land before the DELETE.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import SessionGuardHarness from './SessionGuardHarness.vue';
import SessionUnavailableNotice from '../../src/pages/SessionUnavailableNotice.vue';

const SESSION_URL = '**/api/v1/session';
const HOUR_MS = 60 * 60 * 1000;
const T0 = new Date('2026-11-10T08:00:00Z').getTime();

const SESSION_PAYLOAD = {
  units: [],
  configured_years: [],
  min_configurable_year: 2020,
  user: { id: 7, email: 'someone@epfl.ch', roles_raw: [] },
};

test('a 503 at bootstrap is not a logout, and the next navigation retries', async ({
  page,
  mount,
}) => {
  const calls: string[] = [];
  await page.route(SESSION_URL, async (route) => {
    calls.push(route.request().method());
    if (calls.length === 1) {
      await route.fulfill({ status: 503, json: { detail: 'down' } });
      return;
    }
    await route.fulfill({ json: SESSION_PAYLOAD });
  });
  const component = await mount(SessionGuardHarness);

  await component.getByTestId('guard').click();
  await expect(component.getByTestId('result')).toHaveText('false');
  await expect(component.getByTestId('unavailable')).toHaveText('true');

  await component.getByTestId('guard').click();
  await expect(component.getByTestId('result')).toHaveText('true');
  await expect(component.getByTestId('user')).toHaveText('user:7');
  await expect(component.getByTestId('unavailable')).toHaveText('false');
  expect(calls).toEqual(['GET', 'GET']);
});

test('a network error at bootstrap is not a logout either', async ({
  page,
  mount,
}) => {
  await page.route(SESSION_URL, (route) => route.abort());
  const component = await mount(SessionGuardHarness);

  await component.getByTestId('guard').click();

  await expect(component.getByTestId('result')).toHaveText('false');
  await expect(component.getByTestId('unavailable')).toHaveText('true');
});

test('the guard re-checks after an hour, and a failed re-check keeps the user', async ({
  page,
  mount,
}) => {
  await page.clock.setFixedTime(T0);
  const calls: string[] = [];
  await page.route(SESSION_URL, async (route) => {
    calls.push(route.request().method());
    if (calls.length === 1) {
      await route.fulfill({ json: SESSION_PAYLOAD });
      return;
    }
    await route.fulfill({ status: 503, json: { detail: 'down' } });
  });
  const component = await mount(SessionGuardHarness);

  await component.getByTestId('guard').click();
  await expect(component.getByTestId('result')).toHaveText('true');
  await component.getByTestId('guard').click();
  await expect(component.getByTestId('result')).toHaveText('true');
  expect(calls).toEqual(['GET']);

  await page.clock.setFixedTime(T0 + HOUR_MS + 1000);
  await component.getByTestId('guard').click();

  await expect.poll(() => calls).toEqual(['GET', 'GET']);
  await expect(component.getByTestId('result')).toHaveText('true');
  await expect(component.getByTestId('user')).toHaveText('user:7');
  await expect(component.getByTestId('unavailable')).toHaveText('false');
});

test('logout waits for a session check in flight before the DELETE', async ({
  page,
  mount,
}) => {
  await page.clock.setFixedTime(T0);
  const events: string[] = [];
  await page.route(SESSION_URL, async (route) => {
    const method = route.request().method();
    events.push(method);
    if (method === 'GET' && events.length > 1) {
      // The re-check answers late: long enough for an early DELETE to show.
      await new Promise((resolve) => setTimeout(resolve, 500));
      events.push('GET answered');
    }
    await route.fulfill({ json: method === 'GET' ? SESSION_PAYLOAD : {} });
  });
  const component = await mount(SessionGuardHarness);
  await component.getByTestId('guard').click();
  await expect(component.getByTestId('result')).toHaveText('true');

  await page.clock.setFixedTime(T0 + HOUR_MS + 1000);
  await component.getByTestId('guard').click();
  await expect.poll(() => events.length).toBe(2);
  await component.getByTestId('logout').click();

  await expect
    .poll(() => events)
    .toEqual(['GET', 'GET', 'GET answered', 'DELETE']);
});

test('the unavailable notice offers a retry', async ({ mount }) => {
  const component = await mount(SessionUnavailableNotice);

  await expect(
    component.getByText('The CO₂ Calculator cannot be reached'),
  ).toBeVisible();
  await expect(
    component.getByTestId('session-unavailable-retry'),
  ).toBeVisible();
});
