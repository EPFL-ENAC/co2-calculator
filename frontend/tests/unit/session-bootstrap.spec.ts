/**
 * Regression tests for the session bootstrap contract (#2943).
 *
 * Before, an anonymous page load was GET /session 401 followed by a
 * POST /session refresh attempt that also 401'd. Now the backend answers
 * 200 without `user` when anonymous, and a 401 (expired or refused cookie)
 * is final: one request either way, nothing else fired, no retry.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import SessionBootstrapHarness from './SessionBootstrapHarness.vue';

const SESSION_URL = '**/api/v1/session';

const ANONYMOUS_PAYLOAD = {
  units: [],
  configured_years: [],
  min_configurable_year: 2020,
};

test('200 without user is anonymous, in exactly one request', async ({
  page,
  mount,
}) => {
  const calls: string[] = [];
  await page.route(SESSION_URL, async (route) => {
    calls.push(route.request().method());
    await route.fulfill({ json: ANONYMOUS_PAYLOAD });
  });

  const component = await mount(SessionBootstrapHarness);

  await expect(component).toHaveText('anonymous');
  expect(calls).toEqual(['GET']);
});

test('401 is anonymous too, with no refresh attempt', async ({
  page,
  mount,
}) => {
  const calls: string[] = [];
  await page.route(SESSION_URL, async (route) => {
    calls.push(route.request().method());
    await route.fulfill({ status: 401, json: { detail: 'Not authenticated' } });
  });

  const component = await mount(SessionBootstrapHarness);

  await expect(component).toHaveText('anonymous');
  expect(calls).toEqual(['GET']);
});

test('a session payload hydrates the user', async ({ page, mount }) => {
  await page.route(SESSION_URL, async (route) => {
    await route.fulfill({
      json: {
        ...ANONYMOUS_PAYLOAD,
        user: { id: 7, email: 'someone@epfl.ch', roles_raw: [] },
      },
    });
  });

  const component = await mount(SessionBootstrapHarness);

  await expect(component).toHaveText('user:7');
});

test('a 500 is an error, not a logged-out user', async ({ page, mount }) => {
  await page.route(SESSION_URL, async (route) => {
    await route.fulfill({ status: 500, body: 'boom' });
  });

  const component = await mount(SessionBootstrapHarness);

  await expect(component).toContainText('error:');
});
