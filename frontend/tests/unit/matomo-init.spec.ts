/**
 * #2649 — analytics is off unless an instance is given a Matomo site id, the
 * tracker is cookieless when it is on, and nothing ever addresses Matomo
 * directly: content blockers drop `matomo.js`/`matomo.php` by filename, so
 * both the script and the hits go through our own backend proxy.
 */

import { test, expect } from '@playwright/test';

import {
  isTrackingEnabled,
  matomoInitCommands,
  trackerScriptSrc,
} from '../../src/utils/matomo';

test('no site id → tracking disabled and nothing queued', () => {
  const config = { siteId: '', environment: 'development' };
  expect(isTrackingEnabled(config)).toBe(false);
  expect(matomoInitCommands(config)).toEqual([]);
});

test('a site id enables a cookieless tracker for that instance', () => {
  const commands = matomoInitCommands({ siteId: '42', environment: 'stage' });
  // disableCookies must be queued before anything can be tracked.
  expect(commands[0]).toEqual(['disableCookies']);
  expect(commands).toContainEqual(['setTrackerUrl', '/api/v1/analytics/track']);
  expect(commands).toContainEqual(['setSiteId', '42']);
  expect(commands).toContainEqual(['setCustomDimension', 1, 'stage']);
  // No user identification, ever.
  expect(commands.map(([name]) => name)).not.toContain('setUserId');
});

test('the tracker is fetched from our own origin, under a neutral path', () => {
  // A path ending in matomo.js is blocked by uBlock whoever serves it — that
  // is the whole reason the backend proxy exists (#2649).
  expect(trackerScriptSrc()).toBe('/api/v1/analytics/js');
  const paths = [trackerScriptSrc(), '/api/v1/analytics/track'];
  for (const path of paths) {
    expect(path.startsWith('/')).toBe(true);
    expect(path).not.toContain('matomo.js');
    expect(path).not.toContain('matomo.php');
  }
});
