<script setup lang="ts">
import { outlinedCheckCircle } from '@quasar/extras/material-icons-outlined';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import type { CompareYearsObjectiveGap } from '@/utils/compareYears';
import { nOrDash } from '@/utils/number';

// KPI block for the gap of the latest selected year to its reduction
// objective (issue #2647). Two states, driven by `gap.missing`:
// - missing (emissions still above the target): the share of current
//   emissions left to cut ("-90%") plus the target value;
// - reached (at or below the target): a "goal reached" badge only, under a
//   plain "{year} target" label so the year is not stated twice.
// Kept separate from CompareYearsDialog so the template can be mounted on
// its own in component tests.

export interface CompareYearsObjectiveGapView extends CompareYearsObjectiveGap {
  targetYear: number;
  objectiveTonnes: number;
}

defineProps({
  gap: {
    type: Object as PropType<CompareYearsObjectiveGapView>,
    required: true,
  },
});

const { t } = useI18n();

function formatTonnes(value: number): string {
  return nOrDash(value, {
    options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
  });
}

function formatPct(value: number): string {
  return nOrDash(value * 100, { options: { maximumFractionDigits: 0 } });
}
</script>

<template>
  <div class="compare-years-kpi">
    <div class="compare-years-kpi__label">
      {{
        t(
          gap.missing
            ? 'results_compare_years_gap_label'
            : 'results_compare_years_gap_reached_label',
          { year: gap.targetYear },
        )
      }}
    </div>
    <div class="compare-years-kpi__gap">
      <span
        v-if="gap.missing"
        class="compare-years-kpi__delta text-negative"
        data-testid="compare-years-objective-gap-delta"
      >
        -{{ formatPct(gap.pctMagnitude) }}%
      </span>
      <span
        v-else
        class="compare-years-kpi__delta compare-years-kpi__reached text-positive"
        data-testid="compare-years-objective-gap-reached"
      >
        <q-icon
          :name="outlinedCheckCircle"
          class="compare-years-kpi__reached-icon"
        />
        {{ t('results_compare_years_gap_reached') }}
      </span>
      <span
        v-if="gap.missing"
        class="compare-years-kpi__sub"
        data-testid="compare-years-objective-gap-target"
      >
        {{
          t('results_compare_years_gap_target', {
            year: gap.targetYear,
            value: `${formatTonnes(gap.objectiveTonnes)} ${t(
              'results_units_tonnes',
            )}`,
          })
        }}
      </span>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/css/02-tokens' as tokens;

.compare-years-kpi {
  padding: tokens.$spacing-lg 0;
}

.compare-years-kpi__label {
  letter-spacing: 0.06em;
  font-size: 11px;
  color: var(--semantic-color-text-muted);
  margin-bottom: tokens.$spacing-xs;
}

.compare-years-kpi__gap {
  display: flex;
  align-items: baseline;
  gap: tokens.$spacing-sm;
}

.compare-years-kpi__delta {
  font-size: 22px;
  line-height: 1.1;
}

.compare-years-kpi__reached {
  display: inline-flex;
  align-items: center;
  gap: tokens.$spacing-xs;
  font-size: 20px;
  font-weight: tokens.$text-weight-medium;
}

.compare-years-kpi__reached-icon {
  font-size: 20px;
}

.compare-years-kpi__sub {
  font-size: 13px;
  color: var(--semantic-color-text-muted);
}
</style>
