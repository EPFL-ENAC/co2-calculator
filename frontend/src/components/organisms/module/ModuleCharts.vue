<template>
  <q-card flat class="container" style="padding: 0">
    <q-card-section class="text-left module-charts">
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
          v-if="!loadingTravelData && travelDatasetSource.length > 0"
          :color-scheme="colors.blue"
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
  </q-card>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue';
import { Module } from 'src/constant/modules';
import HeadCountBarChart from 'src/components/molecules/HeadCountBarChart.vue';
import TreeMapModuleChart from 'src/components/charts/TreeMapModuleChart.vue';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { colors } from 'src/constant/charts';

const props = defineProps<{
  type: Module;
  viewUncertainties?: boolean;
}>();

const moduleStore = useModuleStore();
const workspaceStore = useWorkspaceStore();

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

// Fetch travel data on mount and when unit/year changes
// Store automatically refetches after patch/post/delete operations
watch(
  [() => workspaceStore.selectedUnit?.id, () => workspaceStore.selectedYear],
  ([unitId, year]) => {
    if (props.type === 'professional-travel' && unitId && year) {
      moduleStore.getTravelStatsByClass(unitId, String(year));
    }
  },
  { immediate: true },
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
