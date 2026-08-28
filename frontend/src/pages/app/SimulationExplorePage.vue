<template>
  <q-page class="page-grid">
    <q-card flat class="container">
      <q-icon
        name="o_display_settings"
        color="info"
        size="32px"
        class="q-mb-md"
      />
      <h1 class="text-h2 q-mb-md">{{ $t('simulation_explore_page_title') }}</h1>
      <p class="text-body1 q-mb-none">
        {{ $t('simulation_explore_page_intro') }}
      </p>
    </q-card>

    <template v-if="ready">
      <q-skeleton
        v-if="!simulatorReady"
        type="rect"
        height="200px"
        class="full-width"
      />
      <ExploreModuleExpansionList
        v-else
        :modules="modules"
        :unit-id="unitId"
        :year="year"
        :carbon-report-id="carbonReportId"
      />
      <q-skeleton
        v-if="!breakdownReady"
        type="rect"
        height="200px"
        class="full-width"
      />
      <q-card v-else flat bordered>
        <div class="q-pt-lg q-px-lg">
          <h2 class="text-h3 text-weight-medium">
            {{ $t('simulation_explore_page_results_title') }}
          </h2>
        </div>

        <q-separator class="q-mt-lg" />

        <!-- Summary numbers. Gapless grid: each block's own padding is the
             only spacing, so its top and bottom read alike (a gap would land
             above every separator but never at the card edges). Still a grid,
             because BigNumber sizes itself against its row. -->
        <div class="results-blocks">
          <BigNumber
            :title="$t('simulation_explore_page_results_total_tonnes_co2eq')"
            :number="`${formatTonnesCO2(totalTonnesCo2eq)}`"
            comparison=""
            color="info"
            compact
            :bordered="false"
          />

          <q-separator />

          <ModuleCarbonFootprintChart
            :breakdown-data="breakdown"
            :bordered="false"
          />

          <q-separator />

          <div class="column items-center justify-center q-pa-xl q-gutter-md">
            <h3 class="text-h4 text-weight-medium">
              {{ $t('simulation_explore_page_results_download_title') }}
            </h3>
            <q-btn
              unelevated
              no-caps
              icon="o_download"
              :label="$t('simulation_explore_page_results_download_button')"
              size="md"
              color="info"
              class="text-weight-medium"
              @click="downloadReport"
            />
          </div>
        </div>
      </q-card>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

import ExploreModuleExpansionList from '@/components/organisms/module/ExploreModuleExpansionList.vue';
import { useModuleStore } from '@/stores/modules';
import { useWorkspaceStore } from '@/stores/workspace';
import { useYearConfigStore } from '@/stores/yearConfig';
import { getExploreModules } from '@/utils/exploreModules';
import { formatTonnesCO2 } from '@/utils/number';
import BigNumber from '@/components/molecules/BigNumber.vue';
import ModuleCarbonFootprintChart from '@/components/charts/results/ModuleCarbonFootprintChart.vue';

const router = useRouter();
const route = useRoute();
const { locale } = useI18n();

const workspaceStore = useWorkspaceStore();
const yearConfigStore = useYearConfigStore();
const moduleStore = useModuleStore();

function downloadReport() {
  const url = router.resolve({
    name: 'simulation-explore-print',
    params: {
      language: locale.value.split('-')[0],
      unit: route.params.unit,
      year: route.params.year,
    },
  }).href;
  window.open(url, '_blank');
}

// workspaceGuard ensures selectedUnit and selectedYear are always set before
// this route renders. The non-null assertions are safe here; the ready guard
// below prevents the template from rendering if that invariant is ever broken.
const unitId = computed(() => workspaceStore.selectedUnit!.id);
const year = computed(() => workspaceStore.selectedYear!);
const carbonReportId = computed(
  () => workspaceStore.selectedCarbonReport?.id ?? null,
);
const ready = computed(
  () =>
    workspaceStore.selectedUnit != null && workspaceStore.selectedYear != null,
);

const mountPrimaryCharts = ref(false);
const simulatorReady = ref(false);
// Gates the results card: until the Explorer's own breakdown is fetched, the
// shared store still holds the Calculator's data from the workspace guard.
const breakdownReady = ref(false);

const modules = computed(() => getExploreModules(yearConfigStore.getModule));

const totalTonnesCo2eq = computed(() => {
  const breakdown = moduleStore.state.emissionBreakdown;
  if (!breakdown) return 0;

  // Keep consistent with the chart (which shows main categories by default).
  const moduleTotal = (breakdown.module_breakdown ?? []).reduce((sum, row) => {
    const rowTotal = (row.emissions ?? []).reduce((rowSum, e) => {
      return rowSum + (typeof e.value === 'number' ? e.value : 0);
    }, 0);
    return sum + rowTotal;
  }, 0);

  return moduleTotal || breakdown.total_tonnes_co2eq || 0;
});

const breakdown = computed(() => moduleStore.state.emissionBreakdown);

async function fetchEmissionBreakdown() {
  const carbonReportId = workspaceStore.selectedCarbonReport?.id;
  if (!carbonReportId) return;
  await moduleStore.getEmissionBreakdown(carbonReportId, []);
}

onMounted(async () => {
  mountPrimaryCharts.value = true;
  if (unitId.value && year.value) {
    await workspaceStore.selectSimulatorExploreCarbonReport(
      unitId.value,
      year.value,
    );
    // Gate SubModuleSection rendering until the simulator report exists in DB
    // so that module table requests don't 404 before the record is created.
    simulatorReady.value = true;
  }
  // Submodule counts and per-module requests defer to a module's first
  // expansion (ExploreModuleExpansionList) — nothing else needs them eagerly.
  await fetchEmissionBreakdown();
  breakdownReady.value = true;
});
</script>

<style scoped>
.chart-wrapper {
  height: 600px;
}

.results-blocks {
  display: grid;
  grid-template-columns: 1fr;
}
</style>
