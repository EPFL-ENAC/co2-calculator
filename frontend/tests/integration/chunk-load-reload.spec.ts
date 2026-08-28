import { test, expect } from '@playwright/test';

/**
 * Regression test for #2194: after a deploy, a client holding stale chunk
 * hashes gets a "failed to fetch dynamically imported module" / "Unable to
 * preload CSS" / "Importing a module script failed" failure. Before this
 * fix, only the vue-router capture site special-cased this into a reload
 * prompt — a failure surfacing via `unhandledrejection` (e.g. a lazy-loaded
 * component, not a route) fell through to the generic red error toast, and
 * every occurrence was still reported to GlitchTip, paging on every release.
 *
 * This dispatches a real unhandled rejection with a stale-chunk message (the
 * webServer here runs `npm run preview` against the production build, so
 * `import.meta.env.DEV`-gated `window.__gtTest` doesn't exist) and asserts
 * the app shows a blocking, non-dismissible reload prompt instead of the
 * generic error toast.
 */
test('a stale-chunk failure shows a non-dismissible reload prompt, not an error toast', async ({
  page,
}) => {
  // No backend runs against this webServer. Left unmocked, the session
  // check hits a real 404, which api/http.ts's generic error handler toasts
  // — a toast unrelated to the chunk-load failure this test is about, but
  // indistinguishable from it by the assertion below (#2497).
  await page.route(/\/api\/v1\/session$/, (route) =>
    route.fulfill({ status: 401, contentType: 'application/json', body: '{}' }),
  );

  await page.goto('/');
  // Wait for the app to actually be interactive before firing the
  // synthetic rejection: `unhandledrejection` is a point-in-time browser
  // event, not a retryable condition, so dispatching it before
  // boot/sentry.ts's listener is attached means it's silently dropped —
  // this waits for a real readiness signal instead of an arbitrary delay.
  await expect(
    page.getByRole('button', { name: /log ?in/i }).first(),
  ).toBeVisible();

  await page.evaluate(() => {
    void Promise.reject(
      new Error('Unable to preload CSS for /assets/ResultsPage-abc123.css'),
    );
  });

  const dialog = page.locator('.reload-prompt-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Reload' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Later' })).toBeVisible();

  // Persistent: neither Escape nor a backdrop click may dismiss it.
  await page.keyboard.press('Escape');
  await expect(dialog).toBeVisible();
  await page.mouse.click(5, 5);
  await expect(dialog).toBeVisible();

  // Never the generic red error toast for this error class.
  await expect(page.locator('.q-notification')).toHaveCount(0);

  await dialog.getByRole('button', { name: 'Later' }).click();
  await expect(dialog).not.toBeVisible();
});
