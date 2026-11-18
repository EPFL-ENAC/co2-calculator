import { defineConfig } from 'playwright/test';
import process from 'process';
// webServer: {
//   command: 'npm run preview',
//   port: 4173,
//   reuseExistingServer: !process.env.CI
// }

const port = Number(process.env.PREVIEW_PORT ?? 4173);

// The e2e tests run with the example institution of
// frontend/institution-example: `npm run preview` writes it into dist/spa
// with the container script, so CI and local runs are equal (#3244).

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
