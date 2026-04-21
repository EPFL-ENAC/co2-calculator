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
      <div class="flex w-full items-center justify-between q-mx-lg">
        <div class="text-body1 text-weight-medium q-ml-sm q-mb-none text-black">
          {{ carbonFootprintTitle }}
        </div>
        <div class="flex items-center no-wrap q-gutter-xs">
          <q-btn
            v-if="emissionTypeInfoKey && moduleChartView === 'type'"
            flat
            round
            dense
            icon="info_outline"
            size="sm"
            class="text-grey-7"
            :aria-label="t('emission-type-breakdown-info-aria')"
          >
            <q-tooltip
              anchor="bottom right"
              self="top right"
              :offset="[0, 8]"
              max-width="320px"
              class="text-body2"
            >
              {{ t(emissionTypeInfoKey) }}
            </q-tooltip>
          </q-btn>
          <div class="chart-view-toggle">
            <q-btn
              unelevated
              dense
              :style="moduleChartView === 'type' ? activeButtonStyle : {}"
              :class="moduleChartView !== 'type' ? 'toggle-inactive' : ''"
              icon="stacked_bar_chart"
              size="sm"
              @click="moduleChartView = 'type'"
            />
            <q-btn
              unelevated
              dense
              :style="moduleChartView === 'breakdown' ? activeButtonStyle : {}"
              :class="moduleChartView !== 'breakdown' ? 'toggle-inactive' : ''"
              icon="grid_view"
              size="sm"
              @click="moduleChartView = 'breakdown'"
            />
          </div>
        </div>
      </div>
      <q-separator class="q-my-lg" />
      <div class="q-mx-lg">
        <template v-if="moduleChartView === 'breakdown'">
          <generic-emission-tree-map-chart
            v-if="moduleTreemapData.length"
            :key="type"
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
            :key="type"
            :category-rows="moduleCategoryRows"
            :top-class-breakdown="topClassBreakdownData"
          />

          <span v-else class="text-body2 text-secondary">
            {{ $t('no-chart-data') }}
          </span>
        </template>
      </div>
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
  CHART_SUBCATEGORY_COLOR_SCHEMES,
  MODULE_TO_CATEGORIES,
} from 'src/constant/charts';
import { getEmissionTypeBreakdownInfoKey } from 'src/constant/emissionTypeBreakdownInfo';

const props = defineProps<{
  type: Module;
  showEvolutionChart?: boolean;
}>();

const { t, te } = useI18n();

const moduleChartView = ref<'breakdown' | 'type'>('type');

const emissionTypeInfoKey = computed(() =>
  getEmissionTypeBreakdownInfoKey(props.type),
);

const carbonFootprintTitle = computed(() => {
  const moduleKey = `carbon_footprint_title_${props.type}`;
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

const activeButtonStyle = computed((): Record<string, string> => {
  if (props.type === MODULES.Buildings) {
    const roomColor =
      CHART_CATEGORY_COLOR_SCALES.value['buildings_room']?.darker ?? '#00a79f';
    const combustionColor =
      CHART_SUBCATEGORY_COLOR_SCHEMES.value['buildings_energy_combustion']
        ?.combustion ?? '#00a79f';
    return {
      background: `linear-gradient(to right, ${combustionColor}, ${roomColor})`,
      color: '#fff',
    };
  }
  return { backgroundColor: activeColor.value, color: '#fff' };
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

// Re-fetch top-class breakdown when the module type changes (e.g. navigating
// from purchases to equipment) so stale data from the previous module is replaced.
watch(
  () => props.type,
  () => fetchTopClassBreakdownIfNeeded(),
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
  const canonicalizeCategoryKey = (raw: unknown): string => {
    const key = String(raw ?? '');
    return key === 'purchase' ? 'purchases' : key;
  };
  const getRowCategoryKey = (row: Record<string, unknown>): string =>
    canonicalizeCategoryKey(
      (row as { category_key?: unknown }).category_key ?? row.category,
    );

  const filteredKeys = Object.fromEntries(
    Object.entries(CATEGORY_CHART_KEYS).filter(([k]) => categories.includes(k)),
  ) as Record<string, string[]>;
  // Defensive: ensure we only feed rows belonging to this module's categories.
  const filteredRows = breakdown.filter((r) =>
    categories.includes(getRowCategoryKey(r as Record<string, unknown>)),
  );
  return buildModuleTreemapData(filteredRows, filteredKeys);
});

const moduleCategoryRows = computed(() => {
  const breakdown = moduleStore.state.emissionBreakdown;
  if (!breakdown) return [];
  const categories = MODULE_TO_CATEGORIES.value[props.type] ?? [];
  const canonicalizeCategoryKey = (raw: unknown): string => {
    const key = String(raw ?? '');
    return key === 'purchase' ? 'purchases' : key;
  };
  const getRowCategoryKey = (row: Record<string, unknown>): string =>
    canonicalizeCategoryKey(
      (row as { category_key?: unknown }).category_key ?? row.category,
    );

  return breakdown.module_breakdown.filter((row) =>
    categories.includes(
      getRowCategoryKey(row as unknown as Record<string, unknown>),
    ),
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
