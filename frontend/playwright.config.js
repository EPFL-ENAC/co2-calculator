import { defineConfig } from '@playwright/test';
import process from 'process';
// webServer: {
//   command: 'npm run preview',
//   port: 4173,
//   reuseExistingServer: !process.env.CI
// }

const port = Number(process.env.PREVIEW_PORT ?? 4173);

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
    command: `npm run preview -- --port ${port} --strictPort`,
    port,
    reuseExistingServer: !process.env.CI,
  },
});
