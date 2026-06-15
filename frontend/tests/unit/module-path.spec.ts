/**
 * Regression test for the `modules/undefined/null/equipment` 422 bug.
 *
 * On navigation the module fetch could fire before the workspace store had
 * resolved `selectedUnit`/`selectedYear`. The refs stringified to the literals
 * `"undefined"`/`"null"`, which reached the backend as `{unit_id}`/`{year}`
 * path segments and were rejected with 422. `buildModulePath` /
 * `hasValidModuleParams` are the source-of-truth guard that prevents it.
 */

import { test, expect } from '@playwright/test';

import { MODULES } from '../../src/constant/modules';
import {
  buildModulePath,
  hasValidModuleParams,
} from '../../src/utils/modulePath';

test('builds a valid path when unit/year are resolved', () => {
  expect(buildModulePath(MODULES.Equipment, 42, '2026')).toBe(
    'modules/42/2026/equipment',
  );
});

test('rejects unresolved unit/year (the reported bug)', () => {
  expect(hasValidModuleParams(undefined, '2026')).toBe(false);
  expect(hasValidModuleParams(42, null)).toBe(false);
  // String(undefined) / String(null) — the exact values that hit the URL.
  expect(hasValidModuleParams('undefined', 'null')).toBe(false);
});

test('throws rather than emit undefined/null segments', () => {
  expect(() => buildModulePath(MODULES.Equipment, undefined, null)).toThrow();
  expect(() =>
    buildModulePath(MODULES.Equipment, 'undefined', '2026'),
  ).toThrow();
});
