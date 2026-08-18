<script setup lang="ts">
import { onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import PrintReportShell from 'src/components/organisms/print/PrintReportShell.vue';
import CompletionRateBar from 'src/components/organisms/backoffice/reporting/CompletionRateBar.vue';
import ReportingStatCards from 'src/components/organisms/backoffice/reporting/ReportingStatCards.vue';
import ReportingStatCardUnit from 'src/components/organisms/backoffice/reporting/ReportingStatCardUnit.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import CarbonFootPrintPerPersonChart from 'src/components/charts/results/CarbonFootPrintPerPersonChart.vue';
import EmissionBreakdownChart from 'src/components/charts/EmissionBreakdownChart.vue';
import ItFocusBreakdownChart from 'src/components/charts/results/ItFocusBreakdownChart.vue';
import { useBackofficeReportingPrintData } from 'src/composables/print/useBackofficeReportingPrintData';
import { MODULE_STATES } from 'src/constant/moduleStates';
import { toPrintDocumentTitle } from 'src/utils/unitPerimeterLabel';

const { t } = useI18n();

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
  reportingItBreakdown,
  scopeLabel,
  fetchData,
} = useBackofficeReportingPrintData();

const hasData = computed(() => !loading.value && tableTotal.value > 0);
const showStatCards = computed(() => tableRows.value.length !== 1);

onMounted(async () => {
  await fetchData();
  // Chrome seeds the "Save as PDF" filename from the document title.
  document.title = toPrintDocumentTitle(
    scopeLabel.value,
    t('backoffice_reporting_print_combined_title'),
  );
});
</script>

<template>
  <PrintReportShell :loading="loading" :empty="!hasData">
    <!-- Page 1: Title, completion rate, usage stats + aggregate charts -->
    <ReportPage
      :title="$t('backoffice_reporting_print_combined_title')"
      :scope="scopeLabel"
      :page-number="1"
      :is-first="true"
    >
      <h2 class="text-h5 q-mt-none">
        {{ $t('backoffice_reporting_print_combined_title') }}
      </h2>
      <div class="text-body2 text-secondary">{{ scopeLabel }}</div>

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

      <!-- This report aggregates data across an admin-chosen set of years/units
           with no single "current year" loaded into yearConfigStore, so the
           charts' default module/submodule-activation filtering (which reads
           that single-year config) must be disabled here. -->
      <section class="q-mt-md">
        <ModuleCarbonFootprintChart
          :breakdown-data="reportingEmissionBreakdown"
          :print-mode="true"
          :title="$t('backoffice_reporting_aggregated_results_title')"
          :enforce-module-activation="false"
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
          :enforce-module-activation="false"
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
      :title="$t('backoffice_reporting_print_combined_title')"
      :scope="scopeLabel"
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
