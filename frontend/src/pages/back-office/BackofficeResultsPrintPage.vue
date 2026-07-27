<script setup lang="ts">
import { onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import PrintReportShell from 'src/components/organisms/print/PrintReportShell.vue';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import CompletionRateBar from 'src/components/organisms/backoffice/reporting/CompletionRateBar.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import CarbonFootPrintPerPersonChart from 'src/components/charts/results/CarbonFootPrintPerPersonChart.vue';
import EmissionBreakdownChart from 'src/components/charts/EmissionBreakdownChart.vue';
import ItFocusBreakdownChart from 'src/components/charts/results/ItFocusBreakdownChart.vue';
import { useBackofficeResultsPrintData } from 'src/composables/print/useBackofficeResultsPrintData';
import { toPrintDocumentTitle } from 'src/utils/unitPerimeterLabel';

const { t } = useI18n();

const {
  loading,
  reportingEmissionBreakdown,
  validatedCount,
  tableTotal,
  totalTonnes,
  tonnesPerFte,
  perPersonBreakdown,
  validatedCategories,
  headcountValidated,
  availableModules,
  reportingItBreakdown,
  scopeLabel,
  fetchData,
} = useBackofficeResultsPrintData();

const hasData = computed(
  () => !loading.value && reportingEmissionBreakdown.value != null,
);

onMounted(async () => {
  await fetchData();
  // Chrome seeds the "Save as PDF" filename from the document title.
  document.title = toPrintDocumentTitle(
    scopeLabel.value,
    t('backoffice_reporting_print_results_title'),
  );
});
</script>

<template>
  <PrintReportShell :loading="loading" :empty="!hasData">
    <!-- Page 1: Title, scope, big numbers -->
    <ReportPage
      :title="$t('backoffice_reporting_print_results_title')"
      :scope="scopeLabel"
      :page-number="1"
      :is-first="true"
    >
      <h2 class="text-h5 q-mt-none">
        {{ $t('backoffice_reporting_print_results_title') }}
      </h2>
      <div v-if="scopeLabel" class="text-body2 text-secondary q-mb-lg">
        {{ scopeLabel }}
      </div>

      <div class="q-mt-md">
        <CompletionRateBar
          :validated-units="validatedCount"
          :total-units="tableTotal"
          :scope-label="$t('backoffice_reporting_completion_bar_scope_table')"
          :print-mode="true"
        />
      </div>

      <div class="big-numbers-grid q-mt-lg">
        <BigNumber
          :title="$t('results_total_unit_carbon_footprint')"
          :number="
            $nOrDash(totalTonnes, {
              options: {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1,
              },
            })
          "
          color="negative"
          :print-mode="true"
        />
        <BigNumber
          :title="$t('results_carbon_footprint_per_person')"
          :number="
            $nOrDash(tonnesPerFte, {
              options: {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              },
            })
          "
          :unit="$t('results_units_tonnes')"
          :print-mode="true"
        />
      </div>
      <section class="q-mt-md">
        <ModuleCarbonFootprintChart
          :breakdown-data="reportingEmissionBreakdown"
          :print-mode="true"
          :title="$t('backoffice_reporting_aggregated_results_title')"
        />
      </section>
      <section class="q-mt-md">
        <CarbonFootPrintPerPersonChart
          :per-person-breakdown="perPersonBreakdown"
          :validated-categories="validatedCategories"
          :headcount-validated="headcountValidated"
          :show-validation-placeholder="false"
          :print-mode="true"
          :title="$t('backoffice_reporting_aggregated_results_per_fte_title')"
        />
      </section>
    </ReportPage>

    <ReportPage :scope="scopeLabel">
      <section v-if="reportingItBreakdown" class="q-mt-md">
        <ItFocusBreakdownChart
          :data="reportingItBreakdown"
          :print-mode="true"
          :compact="true"
          :title="$t('backoffice_reporting_it_focus_title')"
        />
      </section>
    </ReportPage>

    <!-- One page per module: treemap + emission type breakdown -->
    <ReportPage
      v-for="(mod, i) in availableModules"
      :key="mod"
      :title="$t('backoffice_reporting_print_results_title')"
      :page-number="2 + i"
    >
      <h2 class="text-h5 q-mt-none">{{ $t(mod) }}</h2>
      <div class="q-mt-md">
        <EmissionBreakdownChart
          :breakdown-data="reportingEmissionBreakdown"
          :forced-module="mod"
          height="200px"
        />
      </div>
    </ReportPage>
  </PrintReportShell>
</template>

<style scoped lang="scss">
.big-numbers-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
</style>
