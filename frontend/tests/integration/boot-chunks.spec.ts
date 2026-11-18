import { test, expect } from 'playwright/test';
import { readFileSync, readdirSync } from 'node:fs';

// Catches the boot files (sentry, matomo, router) going back to a fetch that
// starts only after the entry has run: one more round trip on every first load.
const dist = new URL('../../dist/spa/', import.meta.url);

// BOOT_FILES of quasar.config.js. i18n and first-frame have no chunk of
// their own: the chunk groups put them in the entry.
const BOOT_FILES = ['sentry', 'matomo', 'i18n', 'router', 'first-frame'];
const OWN_CHUNK = ['matomo', 'router', 'sentry'];

test('index.html fetches every boot chunk with the entry', () => {
  const html = readFileSync(new URL('index.html', dist), 'utf8');
  const bootChunks = readdirSync(new URL('assets/', dist)).filter((file) =>
    new RegExp(`^(${BOOT_FILES.join('|')})-[\\w-]+\\.js$`).test(file),
  );

  // A boot file that leaves the entry gets its own chunk: this list then
  // changes, and the loop below proves that the new chunk is preloaded.
  expect(bootChunks.map((file) => file.split('-')[0]).sort()).toEqual(
    OWN_CHUNK,
  );
  for (const file of bootChunks) {
    expect(html).toContain(
      `<link rel="modulepreload" crossorigin href="/assets/${file}">`,
    );
  }
});
