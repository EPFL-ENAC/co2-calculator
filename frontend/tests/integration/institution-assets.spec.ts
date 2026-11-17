import { test, expect, type Page } from 'playwright/test';
import { readFileSync } from 'node:fs';
import { parseEnv } from 'node:util';

/**
 * #3244 — the institution comes from the deployment: values from
 * /injectEnv.js, files from /institution/, colors from /theme.css. The run
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
  await page.route('/theme.css', (route) =>
    route.fulfill({
      contentType: 'text/css',
      body: ':root { --theme-accent: #0000ff; }',
    }),
  );
  await page.goto('/');
  const accent = await page.evaluate(() =>
    getComputedStyle(document.documentElement)
      .getPropertyValue('--q-accent')
      .trim(),
  );
  expect(accent).toBe('#0000ff');
});
