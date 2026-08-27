/**
 * Regression test for #2000 — External AI's "Number of users (FTE)" field
 * must default to 0 in the Explorer, never to the Calculator's validated
 * headcount total. `resolveExplorerFormDefaults` is the pure rule
 * `SubModuleSection.vue` feeds into `ModuleForm`'s `formDefaults`, gated so
 * it wins over `defaultFrom: 'total_fte'` in the Explorer.
 */

import { test, expect } from '@playwright/test';
import type { ModuleField } from '../../src/constant/moduleConfig';

import { resolveExplorerFormDefaults } from '../../src/utils/module-table-access';

const fteCountField = {
  id: 'fte_count',
  type: 'number',
  defaultFrom: 'total_fte',
  explorerDefault: 0,
} as ModuleField;

const usageTypeField = {
  id: 'usage_type',
  type: 'select',
} as ModuleField;

test('an explorerDefault field defaults to its fixed value in the Explorer', () => {
  expect(resolveExplorerFormDefaults([fteCountField])).toEqual({
    fte_count: 0,
  });
});

test('a field without explorerDefault is never included', () => {
  expect(resolveExplorerFormDefaults([fteCountField, usageTypeField])).toEqual({
    fte_count: 0,
  });
});

test('0 is a real default, not treated as unset', () => {
  const defaults = resolveExplorerFormDefaults([fteCountField]);
  expect('fte_count' in defaults).toBe(true);
  expect(defaults.fte_count).toBe(0);
});
