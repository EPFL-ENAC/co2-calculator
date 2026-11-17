import { test, expect } from 'playwright/test';
import { readFileSync, readdirSync } from 'node:fs';

// Catches the boot files (sentry, matomo, router) going back to a fetch that
// starts only after the entry has run: one more round trip on every first load.
const dist = new URL('../../dist/spa/', import.meta.url);

test('index.html fetches every boot chunk with the entry', () => {
  const html = readFileSync(new URL('index.html', dist), 'utf8');
  const bootChunks = readdirSync(new URL('assets/', dist)).filter((file) =>
    /^(sentry|matomo|router|i18n)-[\w-]{8}\.js$/.test(file),
  );

  expect(bootChunks.length).toBeGreaterThan(0);
  for (const file of bootChunks) {
    expect(html).toContain(
      `<link rel="modulepreload" crossorigin href="/assets/${file}">`,
    );
  }
});
