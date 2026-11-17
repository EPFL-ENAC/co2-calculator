import { test, expect, type Page } from 'playwright/test';
import { readFileSync } from 'node:fs';
import { parseEnv } from 'node:util';

/**
 * #3244 — the institution comes from the deployment: values and colors
 * inside the page, files from /institution/. The run
 * uses the institution of playwright.config.js, prepared by build/prepare-preview.mjs with the
 * container script.
 */

const institution = parseEnv(
  readFileSync(process.env.INSTITUTION_ENV_FILE ?? '', 'utf8'),
).APP_INSTITUTION_NAME;

// No backend runs against this webServer (see chunk-load-reload.spec.ts).
const stubSession = (page: Page) =>
  page.route(/\/api\/v1\/session$/, (route) =>
    route.fulfill({ status: 401, contentType: 'application/json', body: '{}' }),
  );

test('fonts, logo and icons load from the institution folder', async ({
  page,
}) => {
  await stubSession(page);
  const assetUrls: string[] = [];
  page.on('request', (request) => {
    if (/\.(woff2?|svg|png|ico)(\?|$)/.test(request.url())) {
      assetUrls.push(new URL(request.url()).pathname);
    }
  });

  await page.goto('/');
  const logo = page.locator('.login__logo img');
  await expect(logo).toHaveAttribute('src', '/institution/logo.svg');
  await expect(page).toHaveTitle(new RegExp(institution));
  await expect(page.locator('link[rel="icon"]').first()).toHaveAttribute(
    'href',
    /^\/institution\/favicon/,
  );

  const fonts = assetUrls.filter((path) => /\.woff2?$/.test(path));
  expect(fonts.length).toBeGreaterThan(0);
  expect(fonts.filter((path) => !path.startsWith('/institution/'))).toEqual([]);
});

test('the theme accent colors the buttons', async ({ page }) => {
  await stubSession(page);
  // The theme is inside the page, as in the container: no request loads it.
  const themeRequests: string[] = [];
  page.on('request', (request) => {
    if (/\/(theme\.css|injectEnv\.js)$/.test(request.url())) {
      themeRequests.push(request.url());
    }
  });
  await page.goto('/');
  const accent = await page.evaluate(() =>
    getComputedStyle(document.documentElement)
      .getPropertyValue('--q-accent')
      .trim(),
  );
  // The accent of tests/institution/theme.conf (see playwright.config.js).
  expect(accent).toBe('#424242');
  expect(themeRequests).toEqual([]);
});
