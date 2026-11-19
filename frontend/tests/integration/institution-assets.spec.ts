import { test, expect, type Page } from 'playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parseEnv } from 'node:util';

/**
 * #3244 — the institution comes from the deployment: values from
 * /injectEnv.js, files from /institution/, colors from /theme.css. The run
 * uses the example institution, prepared by build/prepare-preview.mjs with
 * the container script.
 */

const institution = parseEnv(
  readFileSync(
    resolve(import.meta.dirname, '../../institution-example/values.env'),
    'utf8',
  ),
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
  // Status and size of each asset response: a 404 or an empty file fails.
  const assets = new Map<string, { status: number; size: number }>();
  page.on('response', async (response) => {
    const path = new URL(response.url()).pathname;
    if (!/\.(woff2?|svg|png|ico)$/.test(path)) return;
    const body = await response.body().catch(() => Buffer.alloc(0));
    assets.set(path, { status: response.status(), size: body.length });
  });

  await page.goto('/');
  const logo = page.locator('.login__logo img');
  await expect(logo).toHaveAttribute('src', '/institution/logo.svg');
  await expect(page).toHaveTitle(new RegExp(institution));
  await expect(page.locator('link[rel="icon"]').first()).toHaveAttribute(
    'href',
    /^\/institution\/favicon/,
  );

  // The logo is drawn, not only referenced.
  await expect
    .poll(() => logo.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBeGreaterThan(0);
  await page.evaluate(() => document.fonts.ready);

  const fonts = [...assets.keys()].filter((path) => /\.woff2?$/.test(path));
  expect(fonts.length).toBeGreaterThan(0);
  expect(fonts.filter((path) => !path.startsWith('/institution/'))).toEqual([]);
  for (const path of [...fonts, '/institution/logo.svg']) {
    expect(assets.get(path), path).toEqual({
      status: 200,
      size: expect.any(Number),
    });
    expect(assets.get(path)?.size, path).toBeGreaterThan(0);
  }
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
  // The submit button of the login card has color="accent".
  await expect(page.locator('.login__button .q-btn')).toHaveCSS(
    'background-color',
    'rgb(0, 0, 255)',
  );
});
