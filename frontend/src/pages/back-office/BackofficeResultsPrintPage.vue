<script setup lang="ts">
import { onMounted, computed } from 'vue';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import CompletionRateBar from 'src/components/organisms/backoffice/reporting/CompletionRateBar.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import CarbonFootPrintPerPersonChart from 'src/components/charts/results/CarbonFootPrintPerPersonChart.vue';
import EmissionBreakdownChart from 'src/components/charts/EmissionBreakdownChart.vue';
import ItFocusBreakdownChart from 'src/components/charts/results/ItFocusBreakdownChart.vue';
import { useBackofficeResultsPrintData } from 'src/composables/print/useBackofficeResultsPrintData';

const {
  loading,
  years,
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
  fetchData,
} = useBackofficeResultsPrintData();

const hasData = computed(
  () => !loading.value && reportingEmissionBreakdown.value != null,
);

const yearsLabel = computed(() => years.value.join(', '));

function printReport() {
  window.print();
}

onMounted(async () => {
  await fetchData();
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

    <div v-if="loading" class="flex justify-center q-pa-xl print-hide">
      <q-spinner color="accent" size="3em" />
    </div>

    <div v-else-if="hasData" class="report-container">
      <!-- Page 1: Title, scope, big numbers -->
      <ReportPage
        :title="$t('backoffice_reporting_print_results_title')"
        :page-number="1"
        :is-first="true"
      >
        <h2 class="text-h5 q-mt-none">
          {{ $t('backoffice_reporting_print_results_title') }}
        </h2>
        <div v-if="yearsLabel" class="text-body2 text-secondary q-mb-lg">
          {{ yearsLabel }}
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

      <ReportPage>
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
    </div>
  </div>
</template>

<style scoped lang="scss">
.big-numbers-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
</style>
