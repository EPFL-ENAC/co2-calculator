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
      <div class="flex w-full items-center justify-between">
        <div class="text-body1 text-weight-medium q-ml-sm q-mb-none text-black">
          {{ carbonFootprintTitle }}
        </div>
        <div class="q-mb-sm">
          <div class="chart-view-toggle">
            <q-btn
              unelevated
              dense
              :style="
                moduleChartView === 'type'
                  ? { backgroundColor: activeColor, color: '#fff' }
                  : {}
              "
              :class="moduleChartView !== 'type' ? 'toggle-inactive' : ''"
              icon="stacked_bar_chart"
              size="sm"
              @click="moduleChartView = 'type'"
            />
            <q-btn
              unelevated
              dense
              :style="
                moduleChartView === 'breakdown'
                  ? { backgroundColor: activeColor, color: '#fff' }
                  : {}
              "
              :class="moduleChartView !== 'breakdown' ? 'toggle-inactive' : ''"
              icon="grid_view"
              size="sm"
              @click="moduleChartView = 'breakdown'"
            />
          </div>
        </div>
      </div>

      <template v-if="moduleChartView === 'breakdown'">
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
      <template v-else>
        <emission-type-breakdown-chart
          v-if="moduleCategoryRows.length"
          :category-rows="moduleCategoryRows"
          :top-class-breakdown="topClassBreakdownData"
        />
        <span v-else class="text-body2 text-secondary">
          {{ $t('no-chart-data') }}
        </span>
      </template>
    </template>
  </q-card-section>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Module, MODULES } from 'src/constant/modules';
import HeadCountBarChart from 'src/components/molecules/HeadCountBarChart.vue';
import GenericEmissionTreeMapChart from 'src/components/charts/GenericEmissionTreeMapChart.vue';
import EmissionTypeBreakdownChart from 'src/components/charts/results/EmissionTypeBreakdownChart.vue';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import {
  buildModuleTreemapData,
  CATEGORY_CHART_KEYS,
} from 'src/composables/useEmissionTreemap';
import {
  CHART_CATEGORY_COLOR_SCALES,
  MODULE_TO_CATEGORIES,
} from 'src/constant/charts';

const props = defineProps<{
  type: Module;
  showEvolutionChart?: boolean;
}>();

const { t, te } = useI18n();

const moduleChartView = ref<'breakdown' | 'type'>('type');

const carbonFootprintTitle = computed(() => {
  const moduleKey = `carbon_footprint_title.${props.type}`;
  if (te(moduleKey)) return t(moduleKey);
  return t('carbon_footprint_title', { module: t(props.type) });
});

const activeColor = computed(() => {
  const firstCategory = MODULE_TO_CATEGORIES.value[props.type]?.[0];
  const scale =
    CHART_CATEGORY_COLOR_SCALES.value[
      firstCategory as keyof typeof CHART_CATEGORY_COLOR_SCALES.value
    ];
  return scale?.darker ?? '#00a79f';
});

// Modules that support the top-class breakdown chart
const TOP_CLASS_MODULES: Module[] = [
  MODULES.EquipmentElectricConsumption,
  MODULES.Purchase,
];

const moduleStore = useModuleStore();
const workspaceStore = useWorkspaceStore();
const { emissionBreakdownRefreshSequence } = storeToRefs(moduleStore);

const supportsTopClassBreakdown = computed(() =>
  TOP_CLASS_MODULES.includes(props.type),
);

function fetchTopClassBreakdownIfNeeded() {
  const unitId = workspaceStore.selectedUnit?.id;
  const year = workspaceStore.selectedYear;
  if (unitId && year && supportsTopClassBreakdown.value) {
    void moduleStore.getTopClassBreakdown(unitId, String(year), props.type);
  }
}

watch(
  () => workspaceStore.selectedCarbonReport?.id,
  (carbonReportId) => {
    if (carbonReportId) {
      void moduleStore.getEmissionBreakdown(carbonReportId);
      fetchTopClassBreakdownIfNeeded();
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
    fetchTopClassBreakdownIfNeeded();
  },
  { immediate: true },
);

const hasStats = computed(() => {
  const stats = moduleStore.state.data?.stats;
  return !!stats && Object.keys(stats).length > 0;
});

const moduleTreemapData = computed(() => {
  const breakdown = moduleStore.state.emissionBreakdown?.module_breakdown;
  if (!breakdown || breakdown.length === 0) return [];
  const categories = MODULE_TO_CATEGORIES.value[props.type] ?? [];
  const filteredKeys = Object.fromEntries(
    Object.entries(CATEGORY_CHART_KEYS).filter(([k]) => categories.includes(k)),
  ) as Record<string, string[]>;
  return buildModuleTreemapData(
    breakdown as Array<{ category: string; [key: string]: string | number }>,
    filteredKeys,
  );
});

const moduleCategoryRows = computed(() => {
  const breakdown = moduleStore.state.emissionBreakdown;
  if (!breakdown) return [];
  const categories = MODULE_TO_CATEGORIES.value[props.type] ?? [];
  return breakdown.module_breakdown.filter((row) =>
    categories.includes(row.category),
  );
});

const topClassBreakdownData = computed(() => {
  if (!supportsTopClassBreakdown.value) return undefined;
  const data = moduleStore.state.topClassBreakdown;
  if (!data?.length) return undefined;
  return data as Array<{
    name: string;
    value: number;
    children: Array<{ name: string; value: number }>;
  }>;
});
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-charts {
  color: tokens.$graph-color-primary;
  font-weight: tokens.$graph-font-weight;
  font-size: tokens.$graph-font-size;
  line-height: tokens.$graph-line-height;
}

.chart-view-toggle {
  display: inline-flex;

  border-radius: 4px;
  overflow: hidden;

  .q-btn {
    border-radius: 0;
  }

  .toggle-inactive {
    background-color: #eeeeee;
    color: #757575;
  }
}
</style>
