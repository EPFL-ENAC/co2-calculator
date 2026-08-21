/**
 * Regression test for #1995 — Project Planner's "add equipment" form must
 * pre-fill Equipment ID with "Unknown" (editable), while the Calculator and
 * Explorer forms stay untouched. `resolvePlannerFormDefaults` is the pure
 * rule `SubModuleSection.vue` feeds into `ModuleForm`'s `formDefaults`.
 */

import { test, expect } from '@playwright/test';
import type { ModuleField } from '../../src/constant/moduleConfig';

import { resolvePlannerFormDefaults } from '../../src/utils/module-table-access';

const equipmentIdField = {
  id: 'equipment_id',
  type: 'text',
  plannerDefault: 'Unknown',
} as ModuleField;

const equipmentClassField = {
  id: 'equipment_class',
  type: 'select',
} as ModuleField;

test('a plannerDefault field pre-fills in the Planner', () => {
  expect(resolvePlannerFormDefaults([equipmentIdField], true)).toEqual({
    equipment_id: 'Unknown',
  });
});

test('a plannerDefault field is left unset outside the Planner (Explorer/Calculator)', () => {
  expect(resolvePlannerFormDefaults([equipmentIdField], false)).toEqual({});
});

test('a field without plannerDefault is never included', () => {
  expect(
    resolvePlannerFormDefaults([equipmentIdField, equipmentClassField], true),
  ).toEqual({ equipment_id: 'Unknown' });
});
