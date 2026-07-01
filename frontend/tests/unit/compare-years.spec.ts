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
  computeCompareYearsObjectives,
  closestAvailableYear,
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
  expect(computeCompareYearsTotal(YEARS, [2023, 2024], [...ORDER])).toBeCloseTo(
    46,
  );

  // Deselect "equipment": 10 (2023 travel) + 4 (2024 commuting) = 14.
  expect(
    computeCompareYearsTotal(
      YEARS,
      [2023, 2024],
      ['professional_travel', 'commuting'],
    ),
  ).toBeCloseTo(14);

  // Deselect a year: only 2023 equipment + travel = 30.
  expect(computeCompareYearsTotal(YEARS, [2023], [...ORDER])).toBeCloseTo(30);

  // Empty selection → 0.
  expect(computeCompareYearsTotal(YEARS, [], [...ORDER])).toBe(0);
  expect(computeCompareYearsTotal(YEARS, [2023, 2024], [])).toBe(0);
});

const GOALS: ReductionObjectiveGoal[] = [
  { target_year: 2030, reduction_percentage: 0.3, reference_year: 2023 },
  { target_year: 2040, reduction_percentage: 0.5, reference_year: 2023 },
];

test('closest available year picks the nearest year with a positive baseline', () => {
  // reference 2023 → 2023 itself (distance 0).
  expect(closestAvailableYear(YEARS, 2023, [...ORDER])).toBe(2023);
  // reference far in the future → 2024 (closest with data). 2022 has none.
  expect(closestAvailableYear(YEARS, 2030, [...ORDER])).toBe(2024);
  // Only "commuting" has data in 2024 → that's the only positive year.
  expect(closestAvailableYear(YEARS, 2023, ['commuting'])).toBe(2024);
  // No category with data → null.
  expect(closestAvailableYear(YEARS, 2023, ['food'])).toBeNull();
});

test('closest available year resolves ties to the earlier year', () => {
  // reference 2023.5 is equidistant from 2023 and 2024 → earlier (2023).
  expect(closestAvailableYear(YEARS, 2023.5, [...ORDER])).toBe(2023);
});

test('one objective per goal, sorted by target year, baselined on closest year', () => {
  // Both goals reference 2023 (total 30). 2030 → 30×0.7 = 21; 2040 → 30×0.5 = 15.
  const objectives = computeCompareYearsObjectives(YEARS, [...ORDER], GOALS);
  expect(objectives).toEqual([
    { targetYear: 2030, referenceYear: 2023, valueTonnes: 21 },
    { targetYear: 2040, referenceYear: 2023, valueTonnes: 15 },
  ]);
});

test('objective baseline tracks the selected categories', () => {
  // Only "equipment" selected → 2023 baseline 20; last goal 50% → 10.
  const objectives = computeCompareYearsObjectives(YEARS, ['equipment'], GOALS);
  expect(objectives.at(-1)?.valueTonnes).toBeCloseTo(10);
});

test('objectives can be computed over the scope dimension', () => {
  // Scope "2" in 2023 is 20; last goal 50% → 10.
  const objectives = computeCompareYearsObjectives(
    YEARS,
    ['2'],
    GOALS,
    'scopes',
  );
  expect(objectives.at(-1)).toEqual({
    targetYear: 2040,
    referenceYear: 2023,
    valueTonnes: 10,
  });
});

test('objectives is empty without goals or without any positive baseline year', () => {
  expect(computeCompareYearsObjectives(YEARS, [...ORDER], [])).toEqual([]);
  // No category with data anywhere → every goal skipped.
  expect(computeCompareYearsObjectives(YEARS, ['food'], GOALS)).toEqual([]);
});
