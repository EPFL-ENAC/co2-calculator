import { test, expect } from 'playwright/test';

const FONT_SERVER = 'https://enac-it-fonts.epfl.ch/';

/**
 * Every webfont the app asks for comes from the ENAC font server, not from
 * the build output.
 */
test('webfonts load from the EPFL font server, never from the bundle', async ({
  page,
}) => {
  // Keep CI hermetic: off the EPFL network the server answers 403 anyway.
  await page.route(`${FONT_SERVER}**`, (route) => route.abort());
  // No backend runs against this webServer (see chunk-load-reload.spec.ts).
  await page.route(/\/api\/v1\/session$/, (route) =>
    route.fulfill({ status: 401, contentType: 'application/json', body: '{}' }),
  );

  const fontUrls: string[] = [];
  page.on('request', (request) => {
    if (/\.woff2?(\?|$)/.test(request.url())) fontUrls.push(request.url());
  });

  await page.goto('/');
  await expect(
    page.getByRole('button', { name: /log ?in/i }).first(),
  ).toBeVisible();

  expect(fontUrls.length).toBeGreaterThan(0);
  expect(fontUrls.filter((url) => !url.startsWith(FONT_SERVER))).toEqual([]);
});
