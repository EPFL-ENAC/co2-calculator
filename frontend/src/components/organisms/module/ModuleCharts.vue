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
import type {
  EmissionBreakdownResponse,
  EmissionBreakdownCategoryRow,
} from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

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

function getCategoryTotal(row: EmissionBreakdownCategoryRow): number {
  return row.emissions.reduce((total, emission) => {
    return total + (Number(emission.value) || 0);
  }, 0);
}

function buildTreemapChildren(
  row: EmissionBreakdownCategoryRow,
): EmissionTreemapChild[] {
  const direct: EmissionTreemapChild[] = [];
  const grouped = new Map<string, EmissionTreemapChild>();

  for (const emission of row.emissions) {
    const value = Number(emission.value) || 0;
    if (value <= 0) continue;

    const child: EmissionTreemapChild = {
      name: emission.key,
      value,
    };

    if (!emission.parent_key) {
      direct.push(child);
      continue;
    }

    const parent = grouped.get(emission.parent_key);
    if (!parent) {
      grouped.set(emission.parent_key, {
        name: emission.parent_key,
        value,
        children: [child],
      });
      continue;
    }

    parent.value += value;
    parent.children?.push(child);
  }

  return [...direct, ...Array.from(grouped.values())];
}

const props = defineProps<{
  type: Module;
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

function buildTreemapFromRows(
  breakdown: EmissionBreakdownResponse,
  categories: string[],
): EmissionTreemapCategory[] {
  const colorSchemes = CHART_CATEGORY_COLOR_SCHEMES.value;
  return breakdown.module_breakdown
    .filter(
      (item) =>
        categories.includes(item.category) && getCategoryTotal(item) > 0,
    )
    .map((item) => ({
      name: item.category,
      value: getCategoryTotal(item),
      color: colorSchemes[item.category] ?? '#999999',
      children: buildTreemapChildren(item),
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
