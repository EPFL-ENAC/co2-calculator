import { test, expect } from 'playwright/test';

/**
 * #500: another institution rebrands the same bundle with the
 * APP_INSTITUTION_* variables of /injectEnv.js. This serves a custom
 * injectEnv.js and checks the name, the logo and the accent color in the
 * rendered login page.
 */
const LOGO_URL = 'https://branding.example.org/logo.svg';

async function serveInstitution(
  page: import('playwright/test').Page,
  env: Record<string, string>,
): Promise<void> {
  await page.route('**/injectEnv.js', (route) =>
    route.fulfill({
      contentType: 'application/javascript',
      body: `window.injectedEnvVariable = ${JSON.stringify(env)};`,
    }),
  );
  // No backend behind the preview server: answer the session check as
  // anonymous, or its 404 raises an error toast.
  await page.route('**/api/v1/session', (route) =>
    route.fulfill({ status: 401, body: '' }),
  );
  await page.route(LOGO_URL, (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',
    }),
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

test('the configured institution replaces the EPFL name, logo and color', async ({
  page,
}) => {
  await serveInstitution(page, {
    APP_INSTITUTION_NAME: 'Test University',
    APP_INSTITUTION_LOGO_URL: LOGO_URL,
    APP_INSTITUTION_ACCENT_COLOR: '#003366',
  });

  await page.goto('/');

  await expect(page).toHaveTitle('Test University CO2 Calculator');
  await expect(page.locator('.login__logo img').first()).toHaveAttribute(
    'src',
    LOGO_URL,
  );
  const accent = await resolvedAccent(page);
  expect(accent).toBe('rgb(0, 51, 102)');
  await expect(page.getByText('EPFL')).toHaveCount(0);
});

test('no institution variable keeps the EPFL defaults', async ({ page }) => {
  await serveInstitution(page, {});

  await page.goto('/');

  await expect(page).toHaveTitle('EPFL CO2 Calculator');
  await expect(page.locator('.login__logo img').first()).toHaveAttribute(
    'src',
    // The bundled EPFL logo is inlined in the bundle as a data URI.
    /^data:image\/svg/,
  );
  const accent = await resolvedAccent(page);
  expect(accent).toBe('rgb(255, 0, 0)');
});
