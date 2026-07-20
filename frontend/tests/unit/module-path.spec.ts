/**
 * Regression test for unresolved-path segments reaching the backend.
 *
 * Historically the module fetch could fire before the workspace store had
 * resolved its params; refs stringified to `"undefined"`/`"null"` and hit
 * the backend as path segments (422). With identity addressing the guarded
 * value is the carbon report id: `buildModulePath` throws rather than emit
 * a `carbon-reports/undefined/...` request, and `hasValidModuleParams`
 * still guards the unit/year lookup entry points.
 */

import { test, expect } from '@playwright/test';

import { MODULES } from '../../src/constant/modules';
import {
  buildModulePath,
  hasValidModuleParams,
} from '../../src/utils/modulePath';

test('builds a report-addressed path when the report id is resolved', () => {
  expect(buildModulePath(MODULES.Equipment, 42)).toBe(
    'carbon-reports/42/modules/equipment',
  );
});

test('rejects unresolved unit/year lookup params (the reported bug)', () => {
  expect(hasValidModuleParams(undefined, '2026')).toBe(false);
  expect(hasValidModuleParams(42, null)).toBe(false);
  // String(undefined) / String(null) — the exact values that hit the URL.
  expect(hasValidModuleParams('undefined', 'null')).toBe(false);
  expect(hasValidModuleParams(42, '2026')).toBe(true);
});

test('throws rather than emit an undefined/null report id segment', () => {
  expect(() => buildModulePath(MODULES.Equipment, undefined)).toThrow();
  expect(() => buildModulePath(MODULES.Equipment, null)).toThrow();
  expect(() => buildModulePath(MODULES.Equipment, Number.NaN)).toThrow();
});
