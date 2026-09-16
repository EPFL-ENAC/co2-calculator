/**
 * #2071 — the Planner's per-FTE chart draws one bar per results view that
 * has headcount, the Grant Proposal plain and the summed years hatched like
 * PlannerGrantComparisonChart's series. `plannerPerFteRows` is shared by the
 * planner page and its print report so both draw the same bars.
 */

import { test, expect } from '@playwright/test';

import { plannerPerFteRows } from '../../src/utils/plannerPerFte';
import type { EmissionBreakdownResponse } from '../../src/stores/modules';

const withFte = (fte: number, food: number): EmissionBreakdownResponse => ({
  module_breakdown: [],
  additional_breakdown: [],
  per_person_breakdown: { food },
  validated_categories: ['food'],
  headcount_validated: fte > 0,
  buildings_validated: false,
  total_tonnes_co2eq: 0,
  total_fte: fte,
});

const labels = {
  grantLabel: 'Grant proposal',
  yearsLabel: 'Effective',
};

test('a grant plan with year sections draws both bars, the years one hatched', () => {
  const rows = plannerPerFteRows({
    isGrantProposal: true,
    hasYearSections: true,
    grantBreakdown: withFte(4, 0.5),
    yearsBreakdown: withFte(6, 0.4),
    ...labels,
  });
  expect(rows).toEqual([
    {
      label: 'Grant proposal',
      perPersonBreakdown: { food: 0.5 },
      hatched: false,
    },
    {
      label: 'Effective',
      perPersonBreakdown: { food: 0.4 },
      hatched: true,
    },
  ]);
});

test('a plain plan draws one unhatched bar', () => {
  expect(
    plannerPerFteRows({
      isGrantProposal: false,
      hasYearSections: true,
      grantBreakdown: null,
      yearsBreakdown: withFte(2, 0.3),
      ...labels,
    }),
  ).toEqual([
    {
      label: 'Effective',
      perPersonBreakdown: { food: 0.3 },
      hatched: false,
    },
  ]);
});

test('a view without headcount contributes no bar', () => {
  expect(
    plannerPerFteRows({
      isGrantProposal: true,
      hasYearSections: true,
      grantBreakdown: withFte(0, 0),
      yearsBreakdown: null,
      ...labels,
    }),
  ).toEqual([]);
});
