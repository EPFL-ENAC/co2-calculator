/**
 * Regression test for #2459 — `pickDefaultYear` documents "callers must pass
 * a non-empty set" (`Math.max()` on empty returns -Infinity, which serializes
 * to a PATCH-able `null`). `resolveDefaultReferenceYear` is the pure rule
 * `PlannerProjectInfo.vue`'s `defaultReferenceYear()` feeds into, and it must
 * return `null` — not fall through to a -Infinity default — on an empty set.
 */

import { test, expect } from '@playwright/test';

import { resolveDefaultReferenceYear } from '../../src/utils/plannerYearRange';

const CURRENT_YEAR = 2026;

test('no open year at all returns null, not -Infinity', () => {
  expect(resolveDefaultReferenceYear(new Set(), CURRENT_YEAR)).toBeNull();
});

test('last calendar year is used when it is open', () => {
  expect(resolveDefaultReferenceYear(new Set([2023, 2025]), CURRENT_YEAR)).toBe(
    2025,
  );
});

test('falls back to the latest open year when last calendar year is not open', () => {
  expect(resolveDefaultReferenceYear(new Set([2021, 2023]), CURRENT_YEAR)).toBe(
    2023,
  );
});
