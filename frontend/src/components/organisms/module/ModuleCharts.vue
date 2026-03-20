<template>
  <q-card-section class="text-left module-charts q-px-none">
    <template v-if="type === 'headcount'">
      <h2 class="text-h5 text-weight-medium q-mb-none text-bold text-black">
        {{ $t('headcount-charts-title') }}
      </h2>
      <headCountBarChart
        v-if="hasStats"
        :stats="moduleStore?.state?.data?.stats"
      />
      <span v-else class="text-body2 text-secondary">
        {{ $t(`${type}-charts-no-data-message`) }}
      </span>
    </template>
    <template v-else>
      <generic-emission-tree-map-chart
        v-if="moduleTreemapData.length"
        :data="moduleTreemapData"
        :show-evolution-dialog="
          type === MODULES.ProfessionalTravel && showEvolutionChart
        "
      />
      <span v-else class="text-body2 text-secondary">
        {{ $t('no-chart-data') }}
      </span>
    </template>
  </q-card-section>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia';
import { computed, watch } from 'vue';
import { Module, MODULES } from 'src/constant/modules';
import { MODULE_TO_CATEGORIES } from 'src/constant/charts';
import HeadCountBarChart from 'src/components/molecules/HeadCountBarChart.vue';
import GenericEmissionTreeMapChart from 'src/components/charts/GenericEmissionTreeMapChart.vue';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import {
  buildModuleTreemapData,
  CATEGORY_CHART_KEYS,
} from 'src/composables/useEmissionTreemap';

const props = defineProps<{
  type: Module;
  viewUncertainties?: boolean;
  showEvolutionChart?: boolean;
}>();

const moduleStore = useModuleStore();
const workspaceStore = useWorkspaceStore();
const { emissionBreakdownRefreshSequence } = storeToRefs(moduleStore);

watch(
  () => workspaceStore.selectedCarbonReport?.id,
  (carbonReportId) => {
    if (carbonReportId) {
      void moduleStore.getEmissionBreakdown(carbonReportId);
    }
  },
  { immediate: true },
);

watch(
  emissionBreakdownRefreshSequence,
  (sequence) => {
    if (!moduleStore.consumeEmissionBreakdownRefreshRequest(sequence)) return;
    const carbonReportId = workspaceStore.selectedCarbonReport?.id;
    if (!carbonReportId) return;
    moduleStore.invalidateEmissionBreakdown();
    void moduleStore.getEmissionBreakdown(carbonReportId);
  },
  { immediate: true },
);

const hasStats = computed(() => {
  const stats = moduleStore.state.data?.stats;
  return !!stats && Object.keys(stats).length > 0;
});

const moduleTreemapData = computed(() => {
  const breakdown = moduleStore.state.emissionBreakdown;
  if (!breakdown) return [];
  const categories = MODULE_TO_CATEGORIES.value[props.type] ?? [];
  const filteredKeys = Object.fromEntries(
    Object.entries(CATEGORY_CHART_KEYS).filter(([k]) => categories.includes(k)),
  );
  const rows = breakdown.module_breakdown as Array<{
    category: string;
    [key: string]: number | string;
  }>;
  return buildModuleTreemapData(rows, filteredKeys);
});
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-charts {
  // padding: tokens.$graph-card-padding; // Example padding, adjust as needed
  color: tokens.$graph-color-primary; // Use your token for secondary text
  font-weight: tokens.$graph-font-weight;
  font-size: tokens.$graph-font-size;
  line-height: tokens.$graph-line-height;
}
</style>
