<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { nOrDash } from 'src/utils/number';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import CarbonFootPrintPerPersonChart from 'src/components/charts/results/CarbonFootPrintPerPersonChart.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import AdditionalCategoriesSection from 'src/components/organisms/AdditionalCategoriesSection.vue';
import ItFocusSection from 'src/components/organisms/ItFocusSection.vue';
import ResultsPrintModulePage from 'src/components/organisms/print/ResultsPrintModulePage.vue';
import { useResultsPrintData } from 'src/composables/print/useResultsPrintData';
import { useModuleStore } from 'src/stores/modules';

const {
  resultsSummary,
  resultsSummaryLoading,
  currentYear,
  viewAdditionalData,
  co2PerKmKg,
  hasCo2PerKmKg,
  perPersonBreakdown,
  validatedCategories,
  headcountValidatedForPerPerson,
  validatedModulesForPrint,
  getModuleResult,
  getModuleConfig,
  additionalBreakdown,
  commutingRow,
  foodRow,
  wasteRow,
  embodiedEnergyRow,
  embodiedEnergyByCategory,
  adjustedTotalTonnes,
  adjustedTonnesPerFte,
  additionalChartsValidated,
  showItFocusSection,
  modulePagesStart,
  itPageNumber,
  additionalPageNumber,
  initWorkspaceFromRoute,
  fetchAllData,
  loadModulesConfig,
} = useResultsPrintData();

const moduleStore = useModuleStore();
const { t } = useI18n();

const yearComparisonPct = computed(
  () => resultsSummary.value?.unit_totals.year_comparison_percentage ?? null,
);

const totalCarComparison = computed(() => {
  if (!hasCo2PerKmKg.value || !resultsSummary.value) return undefined;
  return t('results_equivalent_to_car', {
    km: nOrDash(resultsSummary.value.unit_totals.equivalent_car_km, {
      options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
    }),
    value: nOrDash(co2PerKmKg.value, {
      options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
    }),
  });
});

const yearComparisonUnit = computed(() => {
  if (yearComparisonPct.value == null)
    return t('results_no_comparison_year_available');
  return t('results_compared_to', { year: (currentYear.value - 1).toString() });
});

const yearComparisonColor = computed(() => {
  if (yearComparisonPct.value == null) return undefined;
  return yearComparisonPct.value < 0 ? 'positive' : 'negative';
});

const yearComparisonText = computed(() => {
  if (yearComparisonPct.value == null || !resultsSummary.value)
    return undefined;
  return t('results_compared_to_value_of', {
    value: `${nOrDash(
      resultsSummary.value.unit_totals.previous_year_total_tonnes_co2eq,
      { options: { minimumFractionDigits: 1, maximumFractionDigits: 1 } },
    )}${t('results_units_tonnes')}`,
  });
});

const yearComparisonHighlight = computed(() => {
  if (yearComparisonPct.value == null || !resultsSummary.value)
    return undefined;
  return `${nOrDash(
    resultsSummary.value.unit_totals.previous_year_total_tonnes_co2eq,
    { options: { minimumFractionDigits: 1, maximumFractionDigits: 1 } },
  )}${t('results_units_tonnes')}`;
});

const fteBigNumberTitle = computed(() => {
  const fte = resultsSummary.value?.unit_totals.total_fte;
  if (fte == null) return t('results_carbon_footprint_per_FTE_no_headcount');
  return t('results_carbon_footprint_per_fte', {
    FTE: nOrDash(fte, { options: { maximumFractionDigits: 1 } }),
  });
});

const percentChangeFormatter = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: 'always',
});

function formatPercentChange(value: number | null | undefined): string {
  if (value == null) return '-';
  return percentChangeFormatter.format(value / 100);
}

function printReport() {
  window.print();
}

onMounted(async () => {
  const carbonReportId = await initWorkspaceFromRoute();
  if (!carbonReportId) return;

  await loadModulesConfig();
  await fetchAllData(carbonReportId);
});
</script>

<template>
  <div class="bg-grey-2 print-report">
    <q-toolbar class="bg-ac text-primary q-py-sm print-toolbar print-hide">
      <q-space />
      <q-btn
        color="accent"
        icon="o_print"
        size="md"
        class="text-weight-medium"
        :label="$t('results_print')"
        @click="printReport"
      />
    </q-toolbar>

    <div
      v-if="resultsSummary && !resultsSummaryLoading"
      class="report-container"
    >
      <ReportPage
        :title="$t('results_print_title')"
        :page-number="1"
        :is-first="true"
      >
        <h2 class="text-h5 q-mt-none report-h2">
          {{ $t('results_print_title') }}
        </h2>
        <div class="text-body2 text-secondary report-subtitle">
          {{ $t('results_subtitle', { year: currentYear }) }}
        </div>

        <div class="grid-3-col q-mt-lg">
          <BigNumber
            :title="$t('results_total_unit_carbon_footprint')"
            :number="
              $nOrDash(adjustedTotalTonnes, {
                options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
              })
            "
            tooltip-placement="comparison"
            :comparison="totalCarComparison"
            :comparison-highlight="`${$nOrDash(
              resultsSummary.unit_totals.equivalent_car_km,
              {
                options: {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                },
              },
            )}km`"
            color="negative"
            :print-mode="true"
          >
            <template v-if="hasCo2PerKmKg" #tooltip>{{
              $t('results-stats-total-unit-carbon-footprint-title', {
                value: $nOrDash(co2PerKmKg, {
                  options: {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  },
                }),
                unit: $t('results_kg_co2eq_per_km'),
              })
            }}</template>
          </BigNumber>

          <BigNumber
            :title="$t('results_unit_carbon_footprint')"
            :number="
              formatPercentChange(
                resultsSummary.unit_totals.year_comparison_percentage,
              )
            "
            :unit="yearComparisonUnit"
            :color="yearComparisonColor"
            :comparison="yearComparisonText"
            :comparison-highlight="yearComparisonHighlight"
            :print-mode="true"
          />

          <BigNumber
            :title="fteBigNumberTitle"
            :number="
              $nOrDash(adjustedTonnesPerFte, {
                options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
              })
            "
            :comparison="
              $t('results_paris_agreement_value', {
                value: `${$nOrDash(2)}${$t('results_units_tonnes')}`,
              })
            "
            :comparison-highlight="`${$nOrDash(2)}${$t('results_units_tonnes')}`"
            color="negative"
            :print-mode="true"
          >
            <template #tooltip>{{
              $t('results-stats-paris-agreement-title')
            }}</template>
          </BigNumber>
        </div>

        <section class="q-mt-md">
          <ModuleCarbonFootprintChart
            :breakdown-data="moduleStore.state.emissionBreakdown"
            :view-additional-data="viewAdditionalData"
            :print-mode="true"
          />
        </section>
        <section class="q-mt-md">
          <CarbonFootPrintPerPersonChart
            :per-person-breakdown="perPersonBreakdown"
            :validated-categories="validatedCategories"
            :headcount-validated="headcountValidatedForPerPerson"
            :view-additional-data="viewAdditionalData"
            :print-mode="true"
          />
        </section>
      </ReportPage>

      <ResultsPrintModulePage
        v-for="(module, idx) in validatedModulesForPrint"
        :key="module"
        :module="module"
        :page-number="idx + modulePagesStart"
        :module-result="getModuleResult(module)"
        :module-config="getModuleConfig(module)"
        :total-fte="resultsSummary.unit_totals.total_fte"
        :has-co2-per-km-kg="hasCo2PerKmKg"
        :co2-per-km-kg="co2PerKmKg"
        :current-year="currentYear"
      />

      <ReportPage
        v-if="showItFocusSection"
        :title="$t('it-focus-title')"
        :page-number="itPageNumber"
      >
        <h2 class="text-h5 q-mt-none">
          {{ $t('it-focus-title') }}
        </h2>
        <div class="text-body2 text-secondary q-mb-md">
          {{ $t('it-focus-subtitle') }}
        </div>

        <ItFocusSection
          :data="moduleStore.state.itBreakdown"
          :loading="moduleStore.state.loadingItBreakdown"
          :co2-per-km-kg="co2PerKmKg"
          :year="currentYear"
          :print-mode="true"
        />
      </ReportPage>

      <ReportPage
        v-if="
          viewAdditionalData &&
          additionalBreakdown.length > 0 &&
          additionalChartsValidated
        "
        :title="$t('results_additional_title')"
        :page-number="additionalPageNumber"
      >
        <h2 class="text-h5 q-mt-none">
          {{ $t('results_additional_title') }}
        </h2>
        <div class="text-body2 text-secondary">
          {{ $t('results_additional_subtitle') }}
        </div>
        <q-card flat bordered class="q-mt-md print-avoid-break">
          <AdditionalCategoriesSection
            :commuting-row="commutingRow"
            :food-row="foodRow"
            :waste-row="wasteRow"
            :embodied-energy-row="embodiedEnergyRow"
            :embodied-energy-by-category="embodiedEnergyByCategory"
            :headcount-validated="
              moduleStore.state.emissionBreakdown?.headcount_validated ?? false
            "
            :buildings-validated="
              moduleStore.state.emissionBreakdown?.buildings_validated ?? false
            "
            :print-mode="true"
          />
        </q-card>
      </ReportPage>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.report-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: tokens.$print-report-container-padding;
  color: tokens.$color-text !important;
}

.toolbar {
  position: sticky;
  top: 0;
  border-bottom: 1px solid var(--half-muted-color);
  z-index: tokens.$print-toolbar-z-index;
}

.module-page-header {
  margin-bottom: 0px;
}

.grid-3-col {
  display: grid;
  grid-template-columns: 1fr;
  gap: tokens.$print-grid-gap;
}

.report-h2 {
  letter-spacing: -0.01em;
}

.report-subtitle {
  line-height: 1.35;
}

.print-card {
  background: tokens.$color-surface;
  border: 1px solid tokens.$print-border-color;
  border-radius: tokens.$radius-default;
  padding: tokens.$print-card-padding;
  box-shadow: tokens.$print-shadow-subtle;
}

.print-card--chart {
  padding: tokens.$print-card-padding-chart;
}

.print-card__eyebrow {
  letter-spacing: 0.08em;
}

.print-avoid-break {
  break-inside: avoid;
  page-break-inside: avoid;
}

@media (min-width: tokens.$breakpoint-desktop-min) {
  .grid-3-col {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media print {
  .grid-3-col {
    grid-template-columns: repeat(3, 1fr);
  }

  .bg-grey-3 {
    background: white !important;
  }

  .print-report :deep(.big-number--print.q-card--bordered) {
    border: none !important;
  }

  .module-page-header {
    margin-bottom: 10px;
  }

  .module-charts-stack {
    gap: 12px;
  }

  /* Reduce Quasar spacing inside embedded chart cards for print */
  .print-card :deep(.q-pa-xl) {
    padding: 12px !important;
  }

  .print-card :deep(.q-mx-lg) {
    margin-left: 0 !important;
    margin-right: 0 !important;
  }

  .print-card :deep(.q-my-lg) {
    margin-top: 10px !important;
    margin-bottom: 10px !important;
  }

  .print-card :deep(.q-separator) {
    margin: 10px 0 !important;
  }

  :deep(a) {
    color: var(--title-color) !important;
    text-decoration: underline !important;
  }
}
</style>
