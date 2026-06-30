/**
 * Unit tests for the "Compare Years" selection/total helpers (issue #834).
 *
 * Pins the pure logic behind the Compare Years dialog: the default year and
 * category selection (only dimensions that carry emissions) and the headline
 * total, which reflects selected years × selected categories so that
 * deselecting a category lowers the displayed total in step with the chart.
 */

import { test, expect } from '@playwright/test';

import type { CompareYearsEntry } from '../../src/stores/modules';
import type { ReductionObjectiveGoal } from '../../src/stores/yearConfig';
import {
  defaultSelectedYears,
  presentCategories,
  computeCompareYearsTotal,
  computeCompareYearsObjective,
} from '../../src/utils/compareYears';

const ORDER = ['equipment', 'professional_travel', 'commuting'] as const;

const YEARS: CompareYearsEntry[] = [
  {
    year: 2022,
    total_tonnes_co2eq: 0,
    modules: {},
    scopes: {},
  },
  {
    year: 2023,
    total_tonnes_co2eq: 30,
    modules: { equipment: 20, professional_travel: 10 },
    scopes: { '2': 20, '3': 10 },
  },
  {
    year: 2024,
    total_tonnes_co2eq: 16,
    modules: { equipment: 12, commuting: 4 },
    scopes: { '2': 12, '3': 4 },
  },
];

test('default year selection skips years with no emissions', () => {
  expect(defaultSelectedYears(YEARS)).toEqual([2023, 2024]);
});

test('present categories follow the given order and drop absent ones', () => {
  // "professional_travel" appears only in 2023, "commuting" only in 2024.
  expect(presentCategories(YEARS, ORDER)).toEqual([
    'equipment',
    'professional_travel',
    'commuting',
  ]);
  // A category never present is excluded.
  expect(presentCategories(YEARS, [...ORDER, 'food'])).not.toContain('food');
});

test('total sums selected years × selected categories', () => {
  // All selected: 20 + 10 + 12 + 4 = 46.
  expect(
    computeCompareYearsTotal(YEARS, [2023, 2024], [...ORDER]),
  ).toBeCloseTo(46);

  // Deselect "equipment": 10 (2023 travel) + 4 (2024 commuting) = 14.
  expect(
    computeCompareYearsTotal(YEARS, [2023, 2024], [
      'professional_travel',
      'commuting',
    ]),
  ).toBeCloseTo(14);

  // Deselect a year: only 2023 equipment + travel = 30.
  expect(
    computeCompareYearsTotal(YEARS, [2023], [...ORDER]),
  ).toBeCloseTo(30);

  // Empty selection → 0.
  expect(computeCompareYearsTotal(YEARS, [], [...ORDER])).toBe(0);
  expect(computeCompareYearsTotal(YEARS, [2023, 2024], [])).toBe(0);
});

const GOALS: ReductionObjectiveGoal[] = [
  { target_year: 2030, reduction_percentage: 0.3, reference_year: 2023 },
  { target_year: 2040, reduction_percentage: 0.5, reference_year: 2023 },
];

test('objective bar uses the last goal on the latest selected year', () => {
  // Latest selected year = 2024, all categories: total 16; last goal 50% → 8.
  const objective = computeCompareYearsObjective(
    YEARS,
    [2023, 2024],
    [...ORDER],
    GOALS,
  );
  expect(objective).toEqual({ targetYear: 2040, valueTonnes: 8 });
});

test('objective baseline tracks selected categories', () => {
  // Latest selected year 2024 with only "equipment" (12) → 12 × 0.5 = 6.
  const objective = computeCompareYearsObjective(
    YEARS,
    [2023, 2024],
    ['equipment'],
    GOALS,
  );
  expect(objective?.valueTonnes).toBeCloseTo(6);
});

test('objective is null without a goal, year, or baseline', () => {
  expect(
    computeCompareYearsObjective(YEARS, [2023, 2024], [...ORDER], []),
  ).toBeNull();
  expect(
    computeCompareYearsObjective(YEARS, [], [...ORDER], GOALS),
  ).toBeNull();
  // 2022 has no emissions → zero baseline → no bar.
  expect(
    computeCompareYearsObjective(YEARS, [2022], [...ORDER], GOALS),
  ).toBeNull();
});
