import { test, expect, type Page } from 'playwright/test';

// The login URL starts its downloads at navigation time (src/router/
// loginPage.ts and the inline script of index.html), not one after another.
const LOGIN_CHUNK = /\/assets\/LoginPage-[\w-]+\.js$/;
const ENTRY_SCRIPT = /\/assets\/index-[\w-]+\.js$/;
const LOGIN_IMAGES = [
  '/institution/logo.svg',
  '/institution/login-illustration.svg',
];
const DELAY_MS = 1500;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// No backend runs against this webServer (see chunk-load-reload.spec.ts).
async function stubSession(page: Page, waitMs = 0): Promise<() => number> {
  let fulfilledAt = Number.POSITIVE_INFINITY;
  await page.route(/\/api\/v1\/session$/, async (route) => {
    await delay(waitMs);
    fulfilledAt = Date.now();
    await route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: '{}',
    });
  });
  return () => fulfilledAt;
}

test.describe('login page downloads in parallel', () => {
  // Catches the login page chunk waiting again for the session call
  // before it starts to download.
  test('requests the login chunk before the session answers', async ({
    page,
  }) => {
    const sessionFulfilledAt = await stubSession(page, DELAY_MS);
    let chunkRequestedAt = Number.POSITIVE_INFINITY;
    page.on('request', (request) => {
      if (LOGIN_CHUNK.test(request.url())) chunkRequestedAt = Date.now();
    });

    await page.goto('/en/login');
    await expect(page.locator('.login__logo img')).toBeVisible();

    expect(chunkRequestedAt).toBeLessThan(sessionFulfilledAt());
  });

  // Catches the logo and the illustration waiting again for the login
  // chunks: index.html must preload them with the entry.
  test('requests the login images before the entry script has loaded', async ({
    page,
  }) => {
    await stubSession(page);
    await page.route(ENTRY_SCRIPT, async (route) => {
      await delay(DELAY_MS);
      await route.continue();
    });
    const requestedAt = new Map<string, number>();
    let entryFinishedAt = Number.POSITIVE_INFINITY;
    page.on('request', (request) => {
      requestedAt.set(new URL(request.url()).pathname, Date.now());
    });
    page.on('requestfinished', (request) => {
      if (ENTRY_SCRIPT.test(request.url())) entryFinishedAt = Date.now();
    });

    await page.goto('/en/login');
    await expect(page.locator('.login__logo img')).toBeVisible();

    for (const image of LOGIN_IMAGES) {
      expect(requestedAt.get(image)).toBeLessThan(entryFinishedAt);
    }
  });

  // Catches the preload links leaking to pages that draw neither image.
  // The login URL is checked first, so the test also fails with no preload.
  test('adds the image preloads on the login page only', async ({ page }) => {
    await stubSession(page);
    const preloads = (image: string) =>
      page.locator(`head link[rel="preload"][as="image"][href="${image}"]`);

    await page.goto('/en/login');
    for (const image of LOGIN_IMAGES) {
      await expect(preloads(image)).toHaveCount(1);
    }

    await page.goto('/en/unauthorized');
    for (const image of LOGIN_IMAGES) {
      await expect(preloads(image)).toHaveCount(0);
    }
  });
});
