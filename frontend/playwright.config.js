import { defineConfig } from '@playwright/test';
import process from 'process';
// webServer: {
//   command: 'npm run preview',
//   port: 4173,
//   reuseExistingServer: !process.env.CI
// }

export default defineConfig({
  testDir: './tests',
  srcDir: './src',
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:4173',
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
  },
  webServer: {
    command: 'npm run preview',
    port: 4173,
    reuseExistingServer: !process.env.CI,
  },
});
