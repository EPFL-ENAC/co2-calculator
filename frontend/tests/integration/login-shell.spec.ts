import { test, expect, type Page } from 'playwright/test';
import loginMessages from '../../src/i18n/login';

// index.html paints the login title before the JavaScript runs (#3244).
// Aborting every script keeps #q-app empty, as on a slow first load.
async function holdBackScripts(page: Page): Promise<void> {
  await page.route(/\/assets\/.*\.js$/, (route) => route.abort());
}

test.describe('static first frame of index.html', () => {
  // Catches a login page that stays blank until the bundle runs, or a title
  // that drifts from login_title of src/i18n/login.ts.
  test('shows the login title in the language of the URL', async ({ page }) => {
    await holdBackScripts(page);
    await page.goto('/en/login');
    await expect(page.locator('#shell')).toBeVisible();
    await expect(page.locator('#shell')).toHaveText(
      loginMessages.login_title.en,
    );
    await page.goto('/fr/login');
    await expect(page.locator('#shell')).toHaveText(
      loginMessages.login_title.fr,
    );
  });

  // Catches the product name flashing on a page that is not the login page.
  test('stays empty outside the login page', async ({ page }) => {
    await holdBackScripts(page);
    for (const path of ['/en/unauthorized', '/']) {
      await page.goto(path);
      await expect(page.locator('#shell')).toBeAttached();
      await expect(page.locator('#shell')).toHaveText('');
    }
  });

  // Catches a title left on screen under the mounted app (#q-app:empty rule).
  test('hides once the app has mounted', async ({ page }) => {
    // No backend runs against this webServer (see chunk-load-reload.spec.ts).
    await page.route(/\/api\/v1\/session$/, (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: '{}',
      }),
    );
    await page.goto('/en/login');
    await expect(page.locator('.login__logo img')).toBeVisible();
    // The shell must exist and hold the title, or toBeHidden proves nothing.
    await expect(page.locator('#shell')).toBeAttached();
    await expect(page.locator('#shell')).toHaveText(
      loginMessages.login_title.en,
    );
    await expect(page.locator('#shell')).toBeHidden();
  });

  // Catches screen readers announcing the title twice (shell + login card).
  test('is hidden from assistive technology', async ({ page }) => {
    await holdBackScripts(page);
    await page.goto('/en/login');
    await expect(page.locator('#shell')).toHaveAttribute('aria-hidden', 'true');
  });
});
