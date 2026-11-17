import { test, expect } from 'playwright/test';
import { readdirSync } from 'node:fs';
import {
  HOME_URL,
  mockHomeBackend,
} from './setup/home-module-visibility-mocks';

// The header and sidebars load as their own chunks, only once a session
// exists (src/router/authenticatedShell.ts, #3244). Vite names a lazy chunk
// after its component: `npx quasar build` emits Co2Header-<hash>.js,
// Co2Sidebar-<hash>.js and Co2ModuleSidebar-<hash>.js in dist/spa/assets.
const LAYOUT_CHUNKS = /^(Co2Header|Co2Sidebar|Co2ModuleSidebar)-[\w-]+\.js$/;

// The e2e webServer serves dist/spa from the frontend folder.
const BUILT_ASSETS = 'dist/spa/assets';

test.describe('signed-in shell', () => {
  // Catches the layout parts going back into the entry bundle: the login
  // page would then download the header and sidebars it never draws.
  test('the login page does not download the layout chunks', async ({
    page,
  }) => {
    // The first-screen chunk groups (quasar.config.js) merge every static
    // import of the entry into index/vendor. With static imports back, no
    // layout chunk is built at all, so the request check alone would pass.
    const built = readdirSync(BUILT_ASSETS).filter((name) =>
      LAYOUT_CHUNKS.test(name),
    );
    expect(built.map((name) => name.split('-')[0]).sort()).toEqual([
      'Co2Header',
      'Co2ModuleSidebar',
      'Co2Sidebar',
    ]);

    const requested: string[] = [];
    page.on('request', (request) => {
      const name = new URL(request.url()).pathname.split('/').pop() ?? '';
      requested.push(name);
    });
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
    await page.waitForLoadState('networkidle');
    expect(requested.filter((name) => LAYOUT_CHUNKS.test(name))).toEqual([]);
  });

  // Catches a signed-in page shown before its header: the beforeResolve hook
  // of src/router/index.ts must wait for the layout chunks. A full revert to
  // static imports passes here by construction; the test above covers it.
  test('the header is drawn in the first frame of the page content', async ({
    page,
  }) => {
    await mockHomeBackend(page);
    // A slow header chunk: without the wait, the content would paint first.
    await page.route(/\/assets\/Co2Header-[\w-]+\.js$/, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await route.continue();
    });
    // Per frame, not per DOM change: the user sees frames. Records whether
    // the header exists in the first frame that holds the home page content.
    await page.addInitScript(() => {
      const check = () => {
        if (document.querySelector('.home-workspace-bar')) {
          document.documentElement.dataset.headerAtFirstContent = String(
            document.querySelector('.q-header') !== null,
          );
          return;
        }
        requestAnimationFrame(check);
      };
      requestAnimationFrame(check);
    });
    await page.goto(HOME_URL);
    await expect(page.locator('.home-workspace-bar')).toBeVisible({
      timeout: 15000,
    });
    await expect(page.locator('html')).toHaveAttribute(
      'data-header-at-first-content',
      'true',
    );
  });
});
