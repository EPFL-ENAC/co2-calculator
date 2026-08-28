/**
 * Regression test for #2440 — a non-validated module (purchases) still
 * appeared in the "carbon footprint per FTE" chart and inflated its total.
 *
 * The persisted `per_fte` section is computed over every bucket regardless of
 * validation (`derive_report_sections` in backend `app/utils/report_stats.py`),
 * so `toEmissionBreakdown` must filter `per_person_breakdown` down to
 * `validated_buckets`, mirroring how the main unit chart zeroes non-validated
 * categories.
 */

import { test, expect } from '@playwright/test';

import type { ReportStats } from '../../src/utils/emissionStatsAdapter';
import { toEmissionBreakdown } from '../../src/utils/emissionStatsAdapter';

const emptyIt = {
  total_kg: 0,
  percentage_of_total: 0,
  per_fte: 0,
  percentage_of_source_modules: 0,
  categories: {},
  cloud_ai_detail: {},
  validated_sources: [],
  top_class_detail: {},
};

function makeStats(overrides: Partial<ReportStats> = {}): ReportStats {
  return {
    buckets: {
      equipment: {
        scope: 3,
        additional: false,
        total_kg: 500,
        by_emission_type: {},
      },
      purchases: {
        scope: 3,
        additional: false,
        total_kg: 12400,
        by_emission_type: {},
      },
      commuting: {
        scope: 3,
        additional: true,
        total_kg: 1000,
        by_emission_type: {},
      },
    },
    per_fte: { equipment: 0.5, purchases: 12.4, commuting: 1.0 },
    validated_buckets: ['equipment', 'commuting'],
    total: 13900,
    total_fte: 1,
    it: emptyIt,
    ...overrides,
  };
}

test('a non-validated bucket is dropped from per_person_breakdown', () => {
  const breakdown = toEmissionBreakdown(makeStats());

  expect(breakdown.per_person_breakdown).toEqual({
    equipment: 0.5,
    commuting: 1.0,
  });
});

test('an excluded module is dropped even when validated', () => {
  const breakdown = toEmissionBreakdown(
    makeStats({ validated_buckets: ['equipment', 'purchases', 'commuting'] }),
    [4],
  );

  expect(breakdown.per_person_breakdown).toEqual({
    purchases: 12.4,
    commuting: 1.0,
  });
});

test('a report with no validated buckets yields an empty per-person chart', () => {
  const breakdown = toEmissionBreakdown(makeStats({ validated_buckets: [] }));

  expect(breakdown.per_person_breakdown).toEqual({});
});
