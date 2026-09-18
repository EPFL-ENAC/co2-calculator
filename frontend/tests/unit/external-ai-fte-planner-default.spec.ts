/**
 * Regression test for #2061 — External AI's "Number of users (FTE)" field
 * pre-fills from the Calculator's validated Headcount total in the Calculator
 * only. In the Planner (Grant Proposal / prefilled) and the Explorer it must
 * start empty, even while the timeline store still carries the Calculator's
 * validated totals from a previous page. `resolveValidatedFteFormDefaults`
 * is the pure rule `SubModuleSection.vue` feeds into `ModuleForm`.
 */

import { test, expect } from '@playwright/test';
import type { ModuleField } from '../../src/constant/moduleConfig';

import { resolveValidatedFteFormDefaults } from '../../src/utils/module-table-access';

const fteCountField = {
  id: 'fte_count',
  type: 'number',
  defaultFrom: 'total_fte',
} as ModuleField;

const usageTypeField = {
  id: 'usage_type',
  type: 'select',
} as ModuleField;

const calculator = { isExplorer: false, isPlanner: false };
const planner = { isExplorer: false, isPlanner: true };
const explorer = { isExplorer: true, isPlanner: false };

test('the Calculator pre-fills the rounded validated FTE total', () => {
  expect(
    resolveValidatedFteFormDefaults(
      [fteCountField, usageTypeField],
      calculator,
      12.4,
    ),
  ).toEqual({ fte_count: 12 });
});

test('the Planner leaves the field empty even with a validated total loaded', () => {
  expect(
    resolveValidatedFteFormDefaults([fteCountField], planner, 12.4),
  ).toEqual({});
});

test('the Explorer leaves the field empty even with a validated total loaded', () => {
  expect(
    resolveValidatedFteFormDefaults([fteCountField], explorer, 12.4),
  ).toEqual({});
});

test('a validated total of 0 or none pre-fills nothing', () => {
  expect(
    resolveValidatedFteFormDefaults([fteCountField], calculator, 0),
  ).toEqual({});
  expect(
    resolveValidatedFteFormDefaults([fteCountField], calculator, undefined),
  ).toEqual({});
});
