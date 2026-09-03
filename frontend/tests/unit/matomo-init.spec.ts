/**
 * #2649 — analytics is off unless an instance is given a Matomo site id, and
 * the tracker is cookieless when it is on.
 */

import { test, expect } from '@playwright/test';

import {
  isTrackingEnabled,
  matomoInitCommands,
  trackerScriptSrc,
} from '../../src/utils/matomo';

const url = 'https://enac-webanalytics.epfl.ch/';

test('no site id → tracking disabled and nothing queued', () => {
  const config = { url, siteId: '', environment: 'development' };
  expect(isTrackingEnabled(config)).toBe(false);
  expect(matomoInitCommands(config)).toEqual([]);
});

test('a site id enables a cookieless tracker for that instance', () => {
  const commands = matomoInitCommands({
    url,
    siteId: '42',
    environment: 'stage',
  });
  // disableCookies must be queued before anything can be tracked.
  expect(commands[0]).toEqual(['disableCookies']);
  expect(commands).toContainEqual([
    'setTrackerUrl',
    'https://enac-webanalytics.epfl.ch/matomo.php',
  ]);
  expect(commands).toContainEqual(['setSiteId', '42']);
  expect(commands).toContainEqual(['setCustomDimension', 1, 'stage']);
  // No user identification, ever.
  expect(commands.map(([name]) => name)).not.toContain('setUserId');
});

test('endpoint works with or without a trailing slash', () => {
  expect(trackerScriptSrc(url)).toBe(
    'https://enac-webanalytics.epfl.ch/matomo.js',
  );
  expect(trackerScriptSrc('https://enac-webanalytics.epfl.ch')).toBe(
    'https://enac-webanalytics.epfl.ch/matomo.js',
  );
});
