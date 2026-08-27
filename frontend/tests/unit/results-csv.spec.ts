/**
 * Regression test for #866 — the Results "empreinte carbone de l'unité" CSV
 * flattened the emission hierarchy.
 *
 * The backend writes a leaf (`class_2 = 0.9486`) AND its parent's sum
 * (`train = 0.9486`) as sibling flat keys on the same category row
 * (`_build_category_row` in `backend/app/utils/emission_category.py`). The old
 * export iterated those flat keys, so a reader saw `class_2`, `business`,
 * `eco`, `train` and `plane` as five same-level rows, with the parent totals
 * double-counting their children.
 *
 * `buildCarbonFootprintCsvRows` reads `emissions[]` instead — the only place
 * `parent_key` survives — and emits one row per leaf, parent in its own column.
 */

import { test, expect } from '@playwright/test';

import type { ReportStats } from '../../src/utils/emissionStatsAdapter';
import { toEmissionBreakdown } from '../../src/utils/emissionStatsAdapter';
import { buildCarbonFootprintCsvRows } from '../../src/utils/results-csv';

/** Export everything; the validation guard has its own test below. */
const allValidated = () => true;

/**
 * A professional-travel row exactly as `datasetSource` yields it: the leaves in
 * `emissions[]`, and the parent sums (`train`, `plane`) present as flat keys.
 */
const travelRow = {
  category: 'Voyages professionnels',
  category_key: 'professional_travel',
  emissions: [
    { key: 'class_2', value: 0.9486, parent_key: 'train' },
    { key: 'business', value: 5.0248, parent_key: 'plane' },
    { key: 'eco', value: 2.4598, parent_key: 'plane' },
  ],
  parent_keys_order: ['train', 'plane'],
  class_2: 0.9486,
  business: 5.0248,
  eco: 2.4598,
  train: 0.9486,
  plane: 7.4846,
};

test('travel leaves carry their mode in the subcategory column', () => {
  const rows = buildCarbonFootprintCsvRows([travelRow], allValidated);

  expect(rows).toEqual([
    {
      category: 'Voyages professionnels',
      subcategory: 'train',
      subcategory2: 'class_2',
      co2: 0.9486,
    },
    {
      category: 'Voyages professionnels',
      subcategory: 'plane',
      subcategory2: 'business',
      co2: 5.0248,
    },
    {
      category: 'Voyages professionnels',
      subcategory: 'plane',
      subcategory2: 'eco',
      co2: 2.4598,
    },
  ]);
});

test('parent totals never become rows of their own', () => {
  // `train` and `plane` are flat keys on the fixture; the old export emitted
  // them as rows, double-counting their children.
  const rows = buildCarbonFootprintCsvRows([travelRow], allValidated);
  const bareParents = rows.filter((r) => r.subcategory2 === '');
  expect(bareParents).toEqual([]);
});

test('a two-level category leaves the third column empty', () => {
  const rows = buildCarbonFootprintCsvRows(
    [
      {
        category: 'Achats',
        category_key: 'purchases',
        emissions: [{ key: 'it_equipment', value: 6.876 }],
        it_equipment: 6.876,
      },
    ],
    allValidated,
  );

  expect(rows).toEqual([
    {
      category: 'Achats',
      subcategory: 'it_equipment',
      subcategory2: '',
      co2: 6.876,
    },
  ]);
});

test("purchases' catch-all is exported as other_purchases", () => {
  // Both equipment and purchases use the bare key `other`; the export must
  // disambiguate, as the chart's `normalizeCategoryRowKeys` already does.
  const rows = buildCarbonFootprintCsvRows(
    [
      {
        category: 'Achats',
        category_key: 'purchases',
        emissions: [{ key: 'other', value: 1.2 }],
      },
      {
        category: 'Équipements',
        category_key: 'equipment',
        emissions: [{ key: 'other', value: 3.4 }],
      },
    ],
    allValidated,
  );

  expect(rows.map((r) => r.subcategory)).toEqual(['other_purchases', 'other']);
});

test('a non-validated category contributes no rows', () => {
  // `zeroNumericValues` zeroes only the flat keys upstream — `emissions[]`
  // still holds the real numbers. Without the guard they would leak into the
  // CSV even though the chart draws the category as empty.
  const rows = buildCarbonFootprintCsvRows(
    [
      {
        category: 'Équipements',
        category_key: 'equipment',
        emissions: [{ key: 'scientific', value: 12.5 }],
        scientific: 0,
      },
    ],
    (categoryKey) => categoryKey !== 'equipment',
  );

  expect(rows).toEqual([]);
});

test('zero-valued and non-numeric emissions are dropped', () => {
  const rows = buildCarbonFootprintCsvRows(
    [
      {
        category: 'Achats',
        category_key: 'purchases',
        emissions: [
          { key: 'services', value: 0 },
          { key: 'vehicles', value: Number.NaN },
          { key: 'ln2', value: 0.5, parent_key: 'additional' },
        ],
      },
    ],
    allValidated,
  );

  expect(rows).toEqual([
    {
      category: 'Achats',
      subcategory: 'additional',
      subcategory2: 'ln2',
      co2: 0.5,
    },
  ]);
});

test('a row without emissions yields nothing', () => {
  const rows = buildCarbonFootprintCsvRows(
    [{ category: 'Déchets', category_key: 'waste' }],
    allValidated,
  );
  expect(rows).toEqual([]);
});
