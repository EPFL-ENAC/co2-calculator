/**
 * APP_DEMO_MODE blocks the whole app behind a notice pointing to the
 * production instance. Only an explicit "true" may turn it on: any other value
 * (unset, empty, typo) must leave the app usable.
 */

import { test, expect } from '@playwright/test';

import { isDemoMode } from '../../src/utils/demoMode';

test('"true" turns demo mode on, case- and whitespace-insensitive', () => {
  expect(isDemoMode('true')).toBe(true);
  expect(isDemoMode('TRUE')).toBe(true);
  expect(isDemoMode(' True ')).toBe(true);
});

test('anything else keeps the app usable', () => {
  expect(isDemoMode(undefined)).toBe(false);
  expect(isDemoMode(false)).toBe(false);
  expect(isDemoMode('')).toBe(false);
  expect(isDemoMode('false')).toBe(false);
  expect(isDemoMode('1')).toBe(false);
  expect(isDemoMode('yes')).toBe(false);
});
