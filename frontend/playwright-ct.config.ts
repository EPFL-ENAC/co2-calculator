import { defineConfig, devices } from '@playwright/experimental-ct-vue';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './tests/unit',
  /* The base directory, relative to the config file, for snapshot files created with toMatchSnapshot and toHaveScreenshot. */
  snapshotDir: './__snapshots__',
  /* Maximum time one test can run for. */
  timeout: 10 * 1000,
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    /* Port to use for Playwright component endpoint. */
    ctPort: 3100,
    /**
     * Playwright Component Testing starts its own Vite instance and does not
     * automatically inherit Quasar's generated Vite configuration.
     *
     * Quasar injects the `@/*` alias (pointing at `/src`) during
     * `quasar dev/build`, so application code resolves correctly there.
     *
     * However, Playwright CT only sees TypeScript path mappings from
     * `.quasar/tsconfig.json`, and Vite/Rollup cannot use TS `paths`
     * without additional configuration.
     *
     * Without `vite-tsconfig-paths` (or equivalent manual aliases),
     * imports such as:
     *
     *   import { useFooStore } from '@/stores/foo'
     *
     * fail at bundle time with:
     *
     *   Rollup failed to resolve import "@/..."
     *
     * The plugin below makes the Playwright CT Vite instance reuse the
     * same path alias defined by Quasar/TypeScript, avoiding alias drift
     * between app runtime, IDE tooling, and component tests.
     */

    ctViteConfig: {
      resolve: {
        alias: {
          '@': resolve(__dirname, './src'),
          // Boot/router/store files import wrapper helpers (defineBoot,
          // defineRouter, ...) from '#q-app'. `quasar dev/build` registers
          // this alias internally (to @quasar/app-vite's `import` export,
          // the real runtime wrappers); Playwright's own Vite instance
          // doesn't know it, and without it Node's resolver falls back to
          // the package's `types` export — a type-only .d.ts that fails
          // to bundle as real code.
          '#q-app': '@quasar/app-vite',
        },
      },
    },
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
