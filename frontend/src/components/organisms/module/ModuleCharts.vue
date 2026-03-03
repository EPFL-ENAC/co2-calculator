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
import { computed } from 'vue';
import { Module, MODULES } from 'src/constant/modules';
import HeadCountBarChart from 'src/components/molecules/HeadCountBarChart.vue';
import GenericEmissionTreeMapChart from 'src/components/charts/GenericEmissionTreeMapChart.vue';
import { useModuleChartData } from 'src/composables/useModuleChartData';
import { buildModuleTreemapData } from 'src/composables/useEmissionTreemap';

const props = defineProps<{
  type: Module;
  viewUncertainties?: boolean;
  showEvolutionChart?: boolean;
}>();

// Use composable to handle module-specific chart data fetching
// This automatically watches for unit/year changes
const { moduleStore } = useModuleChartData();

const hasStats = computed(() => {
  const stats = moduleStore.state.data?.stats;
  return !!stats && Object.keys(stats).length > 0;
});

const moduleTreemapData = computed(() =>
  buildModuleTreemapData(moduleStore.state.emissionBreakdown, props.type),
);
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
