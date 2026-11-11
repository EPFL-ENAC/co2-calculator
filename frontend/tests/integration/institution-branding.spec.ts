import { test, expect } from './setup/test';
import { injectEnvScript } from '../runtimeEnv';

/**
 * #500: another institution rebrands the same bundle with the
 * APP_INSTITUTION_* variables of /injectEnv.js and its own assets folder at
 * /institution/. This serves both and checks the name, the logo, the font and
 * the accent color in the rendered login page.
 */
const TEST_LOGO =
  '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>';
const TEST_FONTS = ":root { --institution-font-family: 'Test Sans', serif; }";

async function serveInstitution(
  page: import('playwright/test').Page,
  env: Record<string, string>,
): Promise<void> {
  await page.route('**/injectEnv.js', (route) =>
    route.fulfill({
      contentType: 'application/javascript',
      body: injectEnvScript(env),
    }),
  );
  // No backend behind the preview server: answer the session check as
  // anonymous, or its 404 raises an error toast.
  await page.route('**/api/v1/session', (route) =>
    route.fulfill({ status: 401, body: '' }),
  );
  await page.route('**/institution/logo.svg', (route) =>
    route.fulfill({ contentType: 'image/svg+xml', body: TEST_LOGO }),
  );
  await page.route('**/institution/fonts.css', (route) =>
    route.fulfill({ contentType: 'text/css', body: TEST_FONTS }),
  );
}

// The color the browser paints for Quasar's accent (buttons, tabs, links).
function resolvedAccent(page: import('playwright/test').Page): Promise<string> {
  return page.evaluate(() => {
    const probe = document.createElement('span');
    probe.style.color = 'var(--q-accent)';
    document.body.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  });
}

test('the configured institution replaces the EPFL name, logo, font and color', async ({
  page,
}) => {
  await serveInstitution(page, {
    APP_INSTITUTION_NAME: 'Test University',
    APP_INSTITUTION_ACCENT_COLOR: '#003366',
  });

  await page.goto('/');

  await expect(page).toHaveTitle('Test University CO2 Calculator');
  const logo = page.locator('.login__logo img').first();
  await expect(logo).toHaveAttribute('src', '/institution/logo.svg');
  await expect
    .poll(() => logo.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBe(10);
  const fontFamily = await page.evaluate(
    () => getComputedStyle(document.body).fontFamily,
  );
  expect(fontFamily).toBe('"Test Sans", serif');
  const accent = await resolvedAccent(page);
  expect(accent).toBe('rgb(0, 51, 102)');
  await expect(page.getByText('EPFL')).toHaveCount(0);
});
