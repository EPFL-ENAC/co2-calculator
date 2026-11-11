// Browser tests against the full Docker Compose stack (#500), not the preview
// server: they need the real backend, Postgres and Keycloak. Start the stack
// first with `make run-keycloak`. Not part of `npm run test:e2e`.
import { defineConfig } from 'playwright/test';

export default defineConfig({
  testDir: './tests/compose',
  timeout: 60000,
  retries: 0,
  use: {
    baseURL: 'http://localhost',
    headless: true,
    viewport: { width: 1280, height: 720 },
  },
});
