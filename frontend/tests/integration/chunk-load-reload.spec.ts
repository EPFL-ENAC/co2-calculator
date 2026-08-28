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
  await page.goto('/');

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
