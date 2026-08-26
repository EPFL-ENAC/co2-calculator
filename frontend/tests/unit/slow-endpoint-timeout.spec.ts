/**
 * Regression test for #2360 — a slow-but-working request must not be
 * aborted by the browser.
 *
 * `ky.create()` in `src/api/http.ts` sets `timeout: REQUEST_TIMEOUT_MS`
 * (590 s) instead of leaving ky's undeclared default of 10 s. Without it,
 * the browser aborts a request the backend is still answering, surfacing
 * to users as a timeout on a healthy system — #2360 was exactly that, on
 * `GET factors/{det}/list`. That specific endpoint no longer exists
 * (#2391 replaced it with the taxonomy lookup), which is precisely why
 * this test targets the shared `api` client directly rather than any one
 * business endpoint: the property under test is the client's configured
 * timeout, not any particular slow route.
 *
 * This test pins the *behaviour*, not the constant: it holds the response
 * past ky's undeclared default and asserts the call still resolves.
 * Setting the client's `timeout` back to (or below) ky's default makes it
 * fail with a TimeoutError.
 *
 * It is deliberately slow (~11 s) — there is no way to observe an
 * AbortSignal timer without outliving it, and a test that only asserted
 * `REQUEST_TIMEOUT_MS > 10_000` would pass even with the client left at
 * ky's default.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import SlowRequestHarness from './fixtures/SlowRequestHarness.vue';

/** ky's undeclared default. The response must outlive this to prove anything. */
const KY_DEFAULT_TIMEOUT_MS = 10_000;
const RESPONSE_DELAY_MS = KY_DEFAULT_TIMEOUT_MS + 1_000;

test('a response slower than ky default still resolves', async ({
  mount,
  page,
}) => {
  test.setTimeout(RESPONSE_DELAY_MS + 20_000);

  await page.route('**/api/v1/diagnostics/slow-request-test', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, RESPONSE_DELAY_MS));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{}',
    });
  });

  const component = await mount(SlowRequestHarness);

  await expect(component.getByTestId('outcome')).toHaveText('resolved', {
    timeout: RESPONSE_DELAY_MS + 10_000,
  });
  await expect(component.getByTestId('error-name')).toHaveText('');
});
