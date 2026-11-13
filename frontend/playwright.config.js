import { defineConfig } from 'playwright/test';
import process from 'process';
// webServer: {
//   command: 'npm run preview',
//   port: 4173,
//   reuseExistingServer: !process.env.CI
// }

const port = Number(process.env.PREVIEW_PORT ?? 4173);

// The e2e tests run with the values of institutions/epfl and the default
// assets (tests/institution gives only theme.conf):
// `npm run preview` writes
// them into dist/spa with the container scripts (build/prepare-preview.mjs).
// The tracked example keeps CI and local runs equal (#3244).
process.env.INSTITUTION_ENV_FILE ??=
  '../institutions/epfl/frontend.env.example';
process.env.INSTITUTION_ASSETS_DIR ??= './tests/institution';

export default defineConfig({
  testDir: './tests',
  srcDir: './src',
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: `http://localhost:${port}`,
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
  },
  webServer: {
    // Not `npm run preview`: that one reads .env.local, and the tests must
    // run on the tracked values, as in CI.
    command: `node build/prepare-preview.mjs && npx vite preview --outDir dist/spa --port ${port} --strictPort`,
    port,
    reuseExistingServer: !process.env.CI,
  },
});
