/**
 * Regression test for #878 — walking is missing from the commuting
 * "Distance in km (%)" doughnut on the Results page.
 *
 * Walking (``commuting__walking``, id 30001) has an emission factor of 0, so
 * the backend never writes it into ``by_emission_type`` (``if val:`` treats
 * 0.0 as falsy). Its kilometres *are* persisted, in ``by_additional_value``.
 * ``buildCategoryRow`` used to enumerate leaves from ``by_emission_type`` only
 * and skip anything with ``kg <= 0``, so walking vanished from both doughnuts
 * and from the shared legend.
 *
 * The adapter now unions both maps and keeps a leaf that has a physical
 * quantity even at zero kg. ``buildDoughnutOption`` then does the per-chart
 * split on its own: quantity > 0 for the distance doughnut, value > 0 for the
 * CO2 one. The numeric row keys (bar chart / treemap) must stay free of the
 * zero-kg leaf.
 */

import { test, expect } from '@playwright/test';
import { createPinia, setActivePinia } from 'pinia';

import { buildDoughnutOption } from '../../src/composables/results/useAdditionalCategoryCharts';
import {
  toEmissionBreakdown,
  type ReportStats,
} from '../../src/utils/emissionStatsAdapter';

/** Emission type ids, mirroring ``backend/app/modules/emissions/taxonomy.py``. */
const WALKING = '30001';
const CAR = '30005';

/** Commuting: 400 km walked (0 kg), 900 km by car (1200 kg). */
function statsWithWalking(): ReportStats {
  return {
    buckets: {
      commuting: {
        scope: 3,
        additional: true,
        total_kg: 1200,
        by_emission_type: { [CAR]: 1200 },
        by_additional_value: { [WALKING]: 400, [CAR]: 900 },
      },
    },
    per_fte: {},
    validated_buckets: ['commuting'],
    total: 1200,
    total_fte: 10,
    it: {
      total_kg: 0,
      percentage_of_total: 0,
      per_fte: 0,
      percentage_of_source_modules: 0,
      categories: {},
      cloud_ai_detail: {},
      validated_sources: [],
      top_class_detail: {},
    },
  };
}

function commutingRow() {
  const breakdown = toEmissionBreakdown(statsWithWalking(), []);
  const row = breakdown.additional_breakdown.find(
    (c) => c.category_key === 'commuting',
  );
  expect(row, 'commuting row is present').toBeTruthy();
  return row!;
}

/** Shape ``AdditionalCategoriesSection.vue`` feeds to the doughnuts. */
function displayEntries() {
  return commutingRow().emissions.map((e) => ({
    key: e.key,
    value: e.value,
    quantity: e.quantity ?? 0,
    quantity_unit: e.quantity_unit ?? 'km',
  }));
}

const labels = { t: (key: string) => key, te: () => false };

function sliceNames(useQuantity: boolean): string[] {
  const option = buildDoughnutOption(
    labels,
    'commuting',
    displayEntries(),
    useQuantity,
  );
  const series = (option.series as { data?: { name: string }[] }[]) ?? [];
  return (series[0]?.data ?? []).map((d) => d.name);
}

test('walking survives the adapter with its kilometres and zero kg', () => {
  const walking = commutingRow().emissions.find((e) => e.key === 'walking');

  expect(walking).toMatchObject({
    emission_type: 'commuting__walking',
    key: 'walking',
    value: 0,
    quantity: 400,
    quantity_unit: 'km',
  });
});

test('zero-kg walking stays out of the CO2 row aggregates', () => {
  const row = commutingRow();

  // Bar chart / treemap keys: an empty walking bar would be noise.
  expect(row.parent_keys_order).not.toContain('walking');
  expect(row.walking).toBeUndefined();
  // The car leaf is unaffected: 1200 kg → 1.2 t.
  expect(row.car).toBeCloseTo(1.2);
});

test('walking shows in the distance doughnut but not the CO2 one', () => {
  // Subcategory colors read the colorblind store.
  setActivePinia(createPinia());


  expect(sliceNames(true)).toEqual(['walking', 'car']);
  expect(sliceNames(false)).toEqual(['car']);
});
