<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import PlannerGrantComparisonChart from 'src/components/charts/results/PlannerGrantComparisonChart.vue';
import PlannerPrintEmissionTypesPage from 'src/components/organisms/print/PlannerPrintEmissionTypesPage.vue';
import PlannerPrintHeadcountTable from 'src/components/organisms/print/PlannerPrintHeadcountTable.vue';
import PlannerPrintYearPage from 'src/components/organisms/print/PlannerPrintYearPage.vue';
import PrintReportShell from 'src/components/organisms/print/PrintReportShell.vue';
import { useProjectPlannerPrintData } from 'src/composables/print/useProjectPlannerPrintData';
import { formatTonnesCO2 } from 'src/utils/number';
import {
  filledYearRange,
  formatYearRange,
  withYearRange,
} from 'src/utils/plannerYearRange';
import { toPrintDocumentTitle } from 'src/utils/unitPerimeterLabel';

const { t } = useI18n();

const {
  loading,
  notFound,
  plan,
  planYears,
  yearRangeLabel,
  scopeLabel,
  planBreakdown,
  grantBreakdown,
  totalTonnesCo2eq,
  grantTotalTonnes,
  yearBreakdowns,
  yearTotalTonnes,
  headcountRows,
  sheets,
  initWorkspaceFromRoute,
  fetchAllData,
} = useProjectPlannerPrintData();

const createdAtLabel = computed(() => {
  const createdAt = plan.value?.created_at;
  if (!createdAt) return '';
  const parsed = new Date(createdAt);
  return Number.isNaN(parsed.getTime())
    ? ''
    : parsed.toLocaleDateString('de-CH');
});

// A grant proposal with planned years carries both views, so the cover opens
// on the comparison chart the planner page shows (#1977).
const showComparison = computed(
  () => plan.value?.is_grant_proposal === true && planYears.value.length > 0,
);

// The Grant Proposal view spans the whole plan; the effective view spans
// only the years that hold data, falling back to the plan's full range
// while every year is still empty.
const grantYearRange = computed(() =>
  formatYearRange(plan.value?.start_year, plan.value?.end_year),
);
const effectiveYearRange = computed(
  () => filledYearRange(planYears.value) || grantYearRange.value,
);
const grantTotalTitle = computed(() =>
  withYearRange(t('planner_results_grant_total_title'), grantYearRange.value),
);
const yearsTotalTitle = computed(() =>
  withYearRange(
    t('planner_results_years_total_title'),
    effectiveYearRange.value,
  ),
);

onMounted(async () => {
  const resolved = await initWorkspaceFromRoute();
  if (!resolved) {
    notFound.value = true;
    loading.value = false;
    return;
  }

  await fetchAllData();

  // Chrome seeds the "Save as PDF" filename from the document title.
  document.title = toPrintDocumentTitle(
    plan.value?.name ?? scopeLabel.value,
    t('planner_print_title'),
  );
});
</script>

<template>
  <PrintReportShell
    :loading="loading"
    :empty="notFound || plan === null"
    :empty-message="$t('project_planner_not_found')"
  >
    <template v-if="plan">
      <ReportPage
        :title="$t('planner_print_title')"
        :scope="scopeLabel"
        :page-number="1"
        :is-first="true"
        flow
      >
        <h2 class="text-h5 q-mt-none report-h2">
          {{ $t('planner_print_title') }}
        </h2>
        <div class="text-body2 text-secondary">{{ plan.name }}</div>

        <dl class="project-facts q-mt-md">
          <div class="project-facts__row">
            <dt>{{ $t('planner_year_selection_label') }}</dt>
            <dd>{{ yearRangeLabel || '–' }}</dd>
          </div>
          <div v-if="plan.creator_name" class="project-facts__row">
            <dt>{{ $t('planner_print_created_by') }}</dt>
            <dd>{{ plan.creator_name }}</dd>
          </div>
          <div v-if="createdAtLabel" class="project-facts__row">
            <dt>{{ $t('planner_print_created_on') }}</dt>
            <dd>{{ createdAtLabel }}</dd>
          </div>
        </dl>

        <div v-if="showComparison" class="row items-stretch no-wrap q-mt-md">
          <BigNumber
            class="col"
            :title="grantTotalTitle"
            :number="formatTonnesCO2(grantTotalTonnes)"
            color="info"
            :print-mode="true"
          />
          <BigNumber
            class="col q-ml-md"
            :title="yearsTotalTitle"
            :number="formatTonnesCO2(totalTonnesCo2eq)"
            :comparison="
              $t('planner_print_total_over_years', {
                count: planYears.length,
              })
            "
            color="info"
            :print-mode="true"
          />
        </div>
        <div v-else-if="plan.is_grant_proposal" class="q-mt-md">
          <BigNumber
            :title="grantTotalTitle"
            :number="formatTonnesCO2(grantTotalTonnes)"
            color="info"
            :print-mode="true"
          />
        </div>
        <div v-else class="q-mt-md">
          <BigNumber
            :title="$t('planner_results_total_tonnes_co2eq')"
            :number="formatTonnesCO2(totalTonnesCo2eq)"
            :comparison="
              $t('planner_print_total_over_years', {
                count: planYears.length,
              })
            "
            color="info"
            :print-mode="true"
          />
        </div>

        <section class="q-mt-md">
          <!-- Boxed like the other report charts, which carry their own card. -->
          <q-card v-if="showComparison" flat bordered class="q-pa-md">
            <PlannerGrantComparisonChart
              :title="
                $t('planner_results_comparison_chart_title', {
                  name: plan.name,
                })
              "
              :grant-breakdown="grantBreakdown"
              :years-breakdown="planBreakdown"
              :grant-year-range="grantYearRange"
              :effective-year-range="effectiveYearRange"
            />
          </q-card>
          <ModuleCarbonFootprintChart
            v-else-if="plan.is_grant_proposal"
            :breakdown-data="grantBreakdown"
            :title="
              $t('planner_results_comparison_chart_title', { name: plan.name })
            "
            :view-additional-data="true"
            :print-mode="true"
            :enforce-module-activation="false"
          />
          <ModuleCarbonFootprintChart
            v-else
            :breakdown-data="planBreakdown"
            :title="$t('planner_results_chart_title', { name: plan.name })"
            :view-additional-data="true"
            :print-mode="true"
            :enforce-module-activation="false"
          />
        </section>

        <p class="text-caption text-secondary q-mt-md q-mb-none">
          {{ $t('planner_print_methodology_note') }}
        </p>
      </ReportPage>

      <template v-for="sheet in sheets" :key="sheet.key">
        <PlannerPrintYearPage
          v-if="sheet.kind === 'year'"
          :year="sheet.year"
          :page-number="sheet.pageNumber"
          :scope="scopeLabel"
          :plan-name="plan.name"
          :breakdown="yearBreakdowns[sheet.year.id] ?? null"
          :total-tonnes="yearTotalTonnes(sheet.year)"
        />

        <PlannerPrintEmissionTypesPage
          v-else-if="sheet.kind === 'emissions'"
          :year="sheet.year"
          :page-number="sheet.pageNumber"
          :scope="scopeLabel"
          :breakdown="yearBreakdowns[sheet.year.id] ?? null"
        />

        <ReportPage
          v-else
          :title="$t('headcount')"
          :scope="scopeLabel"
          :page-number="sheet.pageNumber"
          flow
        >
          <h2 class="text-h5 q-mt-none">{{ $t('headcount') }}</h2>
          <div class="text-body2 text-secondary q-mb-lg">
            {{ $t('planner_print_module_subtitle', { year: sheet.year.year }) }}
          </div>
          <PlannerPrintHeadcountTable
            :rows="headcountRows[sheet.year.id] ?? []"
          />
        </ReportPage>
      </template>
    </template>
  </PrintReportShell>
</template>

<style scoped lang="scss">
.report-h2 {
  letter-spacing: -0.01em;
}

.project-facts {
  margin: 0;
  font-size: 11px;

  &__row {
    display: flex;
    gap: 6px;
  }

  dt {
    opacity: 0.7;
  }

  dd {
    margin: 0;
    font-weight: 600;
  }
}
</style>
