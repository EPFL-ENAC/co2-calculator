<script setup lang="ts">
import { onMounted } from 'vue';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import PrintReportShell from 'src/components/organisms/print/PrintReportShell.vue';
import SimulationExplorePrintModulePage from 'src/components/organisms/print/SimulationExplorePrintModulePage.vue';
import { useSimulationExplorePrintData } from 'src/composables/print/useSimulationExplorePrintData';
import { formatTonnesCO2 } from 'src/utils/number';

const {
  currentYear,
  loading,
  totalTonnesCo2eq,
  filteredBreakdown,
  exploreModules,
  submoduleRows,
  headcountMembers,
  plannerHeadcountRows,
  initWorkspaceFromRoute,
  fetchAllData,
} = useSimulationExplorePrintData();

onMounted(async () => {
  const carbonReportId = await initWorkspaceFromRoute();
  if (!carbonReportId) return;
  await fetchAllData(carbonReportId);
});
</script>

<template>
  <PrintReportShell :loading="loading">
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

    <SimulationExplorePrintModulePage
      v-for="(m, idx) in exploreModules"
      :key="m.type"
      :module="m"
      :page-number="idx + 2"
      :current-year="currentYear"
      :submodule-rows="submoduleRows"
      :headcount-members="headcountMembers"
      :planner-headcount-rows="plannerHeadcountRows"
    />
  </PrintReportShell>
</template>

<style scoped lang="scss">
@media print {
  .bg-grey-3 {
    background: white !important;
  }
}
</style>
