/**
 * Regression test for #2360 — a slow-but-working endpoint must not be
 * aborted by the browser.
 *
 * `ky.create()` in `src/api/http.ts` sets no `timeout`, so ky's **default of
 * 10 s** applies to every request. Nothing declares it, which is what made it
 * easy to miss: `GET factors/{id}/list` returns a whole year's factor catalog
 * (largest measured: 20,915 rows / 1338 ms server-side, #2049) and under load
 * exceeded that ceiling — the browser aborted a request the backend was still
 * answering, surfacing to users as a timeout on a healthy system.
 *
 * The fix sets `timeout: REQUEST_TIMEOUT_MS` on the client itself, so it
 * applies to every call. An earlier attempt raised it only on endpoints with
 * measured cause; a fourth one (#2404) timed out within hours, which is why
 * a hand-maintained "known slow" list was abandoned.
 *
 * This test pins the *behaviour*, not the constant: it holds the response
 * past ky's default and asserts the call still resolves. Remove the client
 * timeout and it fails with a TimeoutError.
 *
 * It is deliberately slow (~11 s) — there is no way to observe an
 * AbortSignal timer without outliving it, and a test that only asserted
 * `REQUEST_TIMEOUT_MS > 10_000` would pass even with the client left at its
 * default.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import SlowFactorsHarness from './fixtures/SlowFactorsHarness.vue';

/** ky's undeclared default. The response must outlive this to prove anything. */
const KY_DEFAULT_TIMEOUT_MS = 10_000;
const RESPONSE_DELAY_MS = KY_DEFAULT_TIMEOUT_MS + 1_000;

test('a factors/list response slower than ky default still resolves', async ({
  mount,
  page,
}) => {
  test.setTimeout(RESPONSE_DELAY_MS + 20_000);

  await page.route('**/api/v1/factors/**/list**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, RESPONSE_DELAY_MS));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { class: 'a', sub_class: null, label: 'A' },
        { class: 'b', sub_class: null, label: 'B' },
      ]),
    });
  });

  const component = await mount(SlowFactorsHarness, {
    props: { submodule: 'scientific', year: '2025' },
  });

  await expect(component.getByTestId('outcome')).toHaveText('resolved', {
    timeout: RESPONSE_DELAY_MS + 10_000,
  });
  await expect(component.getByTestId('error-name')).toHaveText('');
  await expect(component.getByTestId('row-count')).toHaveText('2');
});
