<script setup lang="ts">
import { onMounted, computed } from 'vue';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import CompletionRateBar from 'src/components/organisms/backoffice/reporting/CompletionRateBar.vue';
import ReportingStatCards from 'src/components/organisms/backoffice/reporting/ReportingStatCards.vue';
import ReportingStatCardUnit from 'src/components/organisms/backoffice/reporting/ReportingStatCardUnit.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import CarbonFootPrintPerPersonChart from 'src/components/charts/results/CarbonFootPrintPerPersonChart.vue';
import EmissionBreakdownChart from 'src/components/charts/EmissionBreakdownChart.vue';
import { useBackofficeReportingPrintData } from 'src/composables/print/useBackofficeReportingPrintData';
import { MODULE_STATES } from 'src/constant/moduleStates';

const {
  loading,
  reportingEmissionBreakdown,
  validatedCount,
  tableTotal,
  tableRows,
  usageStats,
  moduleStats,
  totalModules,
  availableModules,
  fetchData,
} = useBackofficeReportingPrintData();

const hasData = computed(() => !loading.value && tableTotal.value > 0);
const showStatCards = computed(() => tableRows.value.length !== 1);

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
      <!-- Page 1: Title, completion rate, usage stats + aggregate charts -->
      <ReportPage
        :title="$t('backoffice_reporting_print_combined_title')"
        :page-number="1"
        :is-first="true"
      >
        <h2 class="text-h5 q-mt-none">
          {{ $t('backoffice_reporting_print_combined_title') }}
        </h2>

        <div class="q-mt-md">
          <CompletionRateBar
            :validated-units="validatedCount"
            :total-units="tableTotal"
            :scope-label="$t('backoffice_reporting_completion_bar_scope_table')"
            :print-mode="true"
          />
        </div>

        <section class="q-mt-lg">
          <ReportingStatCards v-if="showStatCards" :stats="usageStats" />
          <ReportingStatCardUnit
            v-else
            :validated-modules="moduleStats[MODULE_STATES.Validated]"
            :total-modules="totalModules"
          />
        </section>

        <section class="q-mt-md">
          <ModuleCarbonFootprintChart
            :breakdown-data="reportingEmissionBreakdown"
            :print-mode="true"
            :title="$t('backoffice_reporting_aggregated_results_title')"
          />
        </section>
        <section class="q-mt-md">
          <CarbonFootPrintPerPersonChart
            :per-person-breakdown="
              reportingEmissionBreakdown?.per_person_breakdown ?? null
            "
            :validated-categories="
              reportingEmissionBreakdown?.validated_categories ?? null
            "
            :headcount-validated="
              reportingEmissionBreakdown?.headcount_validated ?? false
            "
            :show-validation-placeholder="false"
            :print-mode="true"
            :title="$t('backoffice_reporting_aggregated_results_per_fte_title')"
          />
        </section>
      </ReportPage>

      <!-- One page per module: treemap + emission type breakdown -->
      <ReportPage
        v-for="(mod, i) in availableModules"
        :key="mod"
        :title="$t('backoffice_reporting_print_combined_title')"
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
