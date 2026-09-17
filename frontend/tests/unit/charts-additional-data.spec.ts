/**
 * #2071 — the Explorer and Planner results cards show the per-FTE chart
 * beside the main chart, both driven by one page-level "Additional data"
 * toggle passed down as `viewAdditionalData`. A chart given that prop must
 * not render its own checkbox (two controls would disagree), and the
 * per-FTE chart's "add headcount" placeholder replaces the chart in the
 * simulators, which have no validation step.
 */

import { test, expect } from '@playwright/experimental-ct-vue';
import CarbonFootPrintPerPersonChart from '@/components/charts/results/CarbonFootPrintPerPersonChart.vue';
import ModuleCarbonFootprintChart from '@/components/charts/results/ModuleCarbonFootprintChart.vue';
import PlannerGrantComparisonChart from '@/components/charts/results/PlannerGrantComparisonChart.vue';
import type { EmissionBreakdownResponse } from '@/stores/modules';

const EMPTY_BREAKDOWN: EmissionBreakdownResponse = {
  module_breakdown: [],
  additional_breakdown: [],
  per_person_breakdown: {},
  validated_categories: [],
  headcount_validated: false,
  buildings_validated: false,
  total_tonnes_co2eq: 0,
  total_fte: 0,
};

test('ModuleCarbonFootprintChart hides its checkbox when the page owns the toggle', async ({
  mount,
}) => {
  const component = await mount(ModuleCarbonFootprintChart, {
    props: { breakdownData: EMPTY_BREAKDOWN, viewAdditionalData: true },
  });
  await expect(component.getByRole('checkbox')).toHaveCount(0);
});

test('PlannerGrantComparisonChart hides its checkbox when the page owns the toggle', async ({
  mount,
}) => {
  const own = await mount(PlannerGrantComparisonChart, {
    props: {
      title: 'Plan',
      grantBreakdown: EMPTY_BREAKDOWN,
      yearsBreakdown: EMPTY_BREAKDOWN,
    },
  });
  await expect(own.getByRole('checkbox')).toHaveCount(1);
  await own.unmount();

  const driven = await mount(PlannerGrantComparisonChart, {
    props: {
      title: 'Plan',
      grantBreakdown: EMPTY_BREAKDOWN,
      yearsBreakdown: EMPTY_BREAKDOWN,
      viewAdditionalData: false,
    },
  });
  await expect(driven.getByRole('checkbox')).toHaveCount(0);
});

test('CarbonFootPrintPerPersonChart asks to add headcount in the simulators', async ({
  mount,
}) => {
  const component = await mount(CarbonFootPrintPerPersonChart, {
    props: {
      headcountValidated: false,
      showValidationPlaceholder: true,
      placeholderVariant: 'add',
    },
  });

  await expect(component).toContainText('Add Headcount to see results');
  await expect(component).not.toContainText('Validate');
});
