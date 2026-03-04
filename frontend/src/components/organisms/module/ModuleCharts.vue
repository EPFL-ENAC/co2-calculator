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
import {
  CHART_CATEGORY_COLOR_SCHEMES,
  MODULE_TO_CATEGORIES,
} from 'src/constant/charts';
import HeadCountBarChart from 'src/components/molecules/HeadCountBarChart.vue';
import GenericEmissionTreeMapChart from 'src/components/charts/GenericEmissionTreeMapChart.vue';
import { useModuleStore } from 'src/stores/modules';
import type { EmissionBreakdownResponse } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

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

type EmissionTreemapChild = {
  name: string;
  value: number;
  percentage?: number;
  color?: string;
  children?: EmissionTreemapChild[];
};

type EmissionTreemapCategory = {
  name: string;
  value: number;
  color: string;
  children: EmissionTreemapChild[];
};

type BackendTreemapCategory = {
  name: string;
  value: number;
  children: EmissionTreemapChild[];
};

function buildTreemapFromRows(
  breakdown: EmissionBreakdownResponse,
  categories: string[],
): EmissionTreemapCategory[] {
  const colorSchemes = CHART_CATEGORY_COLOR_SCHEMES.value;
  const backendTreemap = (breakdown.module_treemap ??
    []) as BackendTreemapCategory[];

  return backendTreemap
    .filter(
      (item) =>
        item &&
        typeof item.name === 'string' &&
        categories.includes(item.name) &&
        Number(item.value) > 0 &&
        Array.isArray(item.children) &&
        item.children.length > 0,
    )
    .map((item) => ({
      name: item.name,
      value: Number(item.value),
      color: colorSchemes[item.name] ?? '#999999',
      children: item.children,
    }));
}

function buildModuleTreemapData(
  breakdown: EmissionBreakdownResponse | null,
  moduleKey: string,
): EmissionTreemapCategory[] {
  if (!breakdown) return [];
  const categories = MODULE_TO_CATEGORIES.value[moduleKey] ?? [];
  if (categories.length === 0) return [];
  return buildTreemapFromRows(breakdown, categories);
}

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
