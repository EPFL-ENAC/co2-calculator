import { test, expect } from 'playwright/test';
import { readEnvFile } from '../../build/institution.mjs';

// The title names the institution of the run (playwright.config.js, #3244).
const institution = readEnvFile(
  process.env.INSTITUTION_ENV_FILE ?? '',
).APP_INSTITUTION_NAME;

test('homepage loads', async ({ page }) => {
  await page.goto('/'); // Uses baseURL automatically
  await expect(page).toHaveTitle(`${institution} CO₂ Calculator`);
});

test('the tab title follows a change of language', async ({ page }) => {
  const nameFrDe = readEnvFile(
    process.env.INSTITUTION_ENV_FILE ?? '',
  ).APP_INSTITUTION_NAME_FR_DE;
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
