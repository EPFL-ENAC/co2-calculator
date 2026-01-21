<template>
  <q-card-section class="text-left module-charts q-px-none">
    <template v-if="type === 'my-lab'">
      <h2 class="text-h5 text-weight-medium q-mb-none text-bold text-black">
        {{ $t('my-lab-charts-title') }}
      </h2>
      <headCountBarChart
        v-if="hasStats"
        :stats="moduleStore?.state?.data?.stats"
      />
      <span v-else class="text-body2 text-secondary">
        {{ $t(`${type}-charts-no-data-message`) }}
      </span>
    </template>
    <template v-else-if="type === 'professional-travel'">
      <tree-map-module-chart
        v-if="
          !loadingTravelData &&
          travelDatasetSource &&
          travelDatasetSource.length > 0
        "
        :show-evolution-dialog="showEvolutionChart"
        :color-scheme="colors.babyBlue"
        :dataset-source="travelDatasetSource"
      />
      <div v-else-if="loadingTravelData" class="text-body2 text-secondary">
        Loading chart data...
      </div>
      <div v-else class="text-body2 text-secondary">
        No travel data available
      </div>
    </template>
    <h2 v-else class="text-h3 q-mb-none text-bold text-uppercase">
      {{ $t(`${type}-charts-title`) }}
    </h2>
  </q-card-section>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue';
import { Module } from 'src/constant/modules';
import HeadCountBarChart from 'src/components/molecules/HeadCountBarChart.vue';
import TreeMapModuleChart from 'src/components/charts/TreeMapModuleChart.vue';
import { useModuleChartData } from 'src/composables/useModuleChartData';
import { colors } from 'src/constant/charts';

const props = defineProps<{
  type: Module;
  viewUncertainties?: boolean;
  showEvolutionChart?: boolean;
}>();

// Use composable to handle module-specific chart data fetching
// This automatically watches for unit/year changes
const { moduleStore } = useModuleChartData(toRef(props, 'type'));

const hasStats = computed(() => {
  const stats = moduleStore.state.data?.stats;
  return !!stats && Object.keys(stats).length > 0;
});

const travelDatasetSource = computed(
  () => moduleStore.state.travelStatsByClass,
);
const loadingTravelData = computed(
  () => moduleStore.state.loadingTravelStatsByClass,
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
