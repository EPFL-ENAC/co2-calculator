import { test, expect } from 'playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parseEnv } from 'node:util';

// The title names the example institution of the run (#3244).
const values = parseEnv(
  readFileSync(
    resolve(import.meta.dirname, '../../institution-example/values.env'),
    'utf8',
  ),
);
const institution = values.APP_INSTITUTION_NAME;

test('homepage loads', async ({ page }) => {
  await page.goto('/'); // Uses baseURL automatically
  await expect(page).toHaveTitle(`${institution} CO₂ Calculator`);
});

test('the tab title follows a change of language', async ({ page }) => {
  const nameFrDe = values.APP_INSTITUTION_NAME_FR_DE;
  // No backend runs against this webServer (see chunk-load-reload.spec.ts).
  await page.route(/\/api\/v1\/session$/, (route) =>
    route.fulfill({ status: 401, contentType: 'application/json', body: '{}' }),
  );
  await page.goto('/en/login');
  // The first navigation is done once the login page shows.
  await expect(page.locator('.login__logo img')).toBeVisible();
  await expect(page).toHaveTitle(`${institution} CO₂ Calculator`);
  // A client-side navigation, as the language links of the header do.
  await page.evaluate(() => {
    history.pushState(null, '', '/fr/login');
    dispatchEvent(new PopStateEvent('popstate', { state: null }));
  });
  await expect(page).toHaveTitle(`Calculateur CO₂ ${nameFrDe}`);
});
