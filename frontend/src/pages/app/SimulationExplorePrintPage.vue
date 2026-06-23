<script setup lang="ts">
import { onMounted } from 'vue';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import { useSimulationExplorePrintData } from 'src/composables/print/useSimulationExplorePrintData';
import { formatTonnesCO2 } from 'src/utils/number';

const {
  currentYear,
  loading,
  totalTonnesCo2eq,
  filteredBreakdown,
  initWorkspaceFromRoute,
  fetchAllData,
} = useSimulationExplorePrintData();

function printReport() {
  window.print();
}

onMounted(async () => {
  const carbonReportId = await initWorkspaceFromRoute();
  if (!carbonReportId) return;
  await fetchAllData(carbonReportId);
});
</script>

<template>
  <div class="bg-grey-2 print-report">
    <q-toolbar class="bg-ac text-primary q-py-sm print-hide">
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

    <div v-if="!loading" class="report-container">
      <ReportPage
        :title="$t('simulation_explore_page_title')"
        :page-number="1"
        :is-first="true"
      >
        <h2 class="text-h5 q-mt-none">
          {{ $t('simulation_explore_page_title') }}
        </h2>
        <div class="text-body2 text-secondary q-mb-lg">
          {{ $t('simulation_explore_print_subtitle', { year: currentYear }) }}
        </div>

        <div class="q-mb-lg">
          <BigNumber
            :title="$t('simulation_explore_page_results_total_tonnes_co2eq')"
            :number="formatTonnesCO2(totalTonnesCo2eq)"
            color="accent"
            :print-mode="true"
          />
        </div>

        <section>
          <ModuleCarbonFootprintChart :breakdown-data="filteredBreakdown" />
        </section>
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

@media print {
  .bg-grey-3 {
    background: white !important;
  }
}
</style>
