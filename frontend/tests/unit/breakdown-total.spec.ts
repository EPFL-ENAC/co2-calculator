/**
 * #2071 — the Explorer and Planner headline total follows the page's
 * "Additional data" toggle: module categories only by default (what the
 * chart draws), plus the additional categories when the toggle is on. It
 * never falls back to the backend's all-buckets total, which used to show
 * a non-zero headline above an empty chart for a headcount-only report.
 */

import { test, expect } from '@playwright/test';

import { sumBreakdownTonnes } from '../../src/utils/breakdownTotal';
import type { EmissionBreakdownResponse } from '../../src/stores/modules';

const row = (
  category: string,
  values: number[],
): EmissionBreakdownResponse['module_breakdown'][number] => ({
  category,
  category_key: category,
  scope: 3,
  additional: false,
  emissions: values.map((value, i) => ({
    emission_type: `${category}__${i}`,
    key: `${category}__${i}`,
    value,
  })),
  parent_keys_order: [],
});

const breakdown: EmissionBreakdownResponse = {
  module_breakdown: [row('purchases', [1.5, 0.5]), row('equipment', [2])],
  additional_breakdown: [row('food', [3]), row('commuting', [1])],
  per_person_breakdown: {},
  validated_categories: [],
  headcount_validated: true,
  buildings_validated: false,
  total_tonnes_co2eq: 8,
  total_fte: 1,
};

test('sums the module categories only by default', () => {
  expect(sumBreakdownTonnes(breakdown)).toBe(4);
});

test('adds the additional categories when asked', () => {
  expect(sumBreakdownTonnes(breakdown, true)).toBe(8);
});

test('a headcount-only report totals zero unless additional data is shown', () => {
  const headcountOnly = { ...breakdown, module_breakdown: [] };
  expect(sumBreakdownTonnes(headcountOnly)).toBe(0);
  expect(sumBreakdownTonnes(headcountOnly, true)).toBe(4);
});

test('leaves out categories the charts hide (embodied energy)', () => {
  const withHidden = {
    ...breakdown,
    additional_breakdown: [
      ...breakdown.additional_breakdown,
      row('embodied_energy', [10]),
    ],
  };
  expect(sumBreakdownTonnes(withHidden, true)).toBe(8);
});

test('no breakdown totals zero', () => {
  expect(sumBreakdownTonnes(null)).toBe(0);
});
