<template>
  <q-card-section class="text-left module-charts q-px-none">
    <!-- Stats are being recomputed by the bulk pipeline (emissions +
         aggregation phases).  Surface a spinner so the charts below —
         which still show the pre-upload numbers until aggregation
         lands — aren't mistaken for the final result. -->
    <div
      v-if="statsRecalculating"
      class="flex items-center q-gutter-sm q-mx-lg q-mb-sm text-secondary"
    >
      <q-spinner size="18px" />
      <span class="text-body2">{{ $t('module_stats_recalculating') }}</span>
    </div>
    <template v-if="type === 'headcount'">
      <div class="q-mx-lg">
        <div class="text-body1 text-weight-medium q-ml-sm q-mb-md text-black">
          {{ $t('headcount-charts-title') }}
        </div>
        <headCountBarChart
          v-if="headcountChartKeys.length"
          :stats="moduleStore?.state?.data?.stats"
        />
        <chart-empty-state v-else />
      </div>
    </template>
    <template v-else>
      <template v-if="!isPrintMode">
        <div class="flex w-full items-center justify-between q-mx-lg">
          <div class="text-body1 text-weight-medium q-ml-sm q-mb-md text-black">
            {{ carbonFootprintTitle }}
          </div>
          <div
            v-if="showControls"
            class="flex items-center no-wrap q-gutter-xs"
          >
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
                :style="typeButtonStyle"
                :class="typeButtonClass"
                icon="stacked_bar_chart"
                size="sm"
                @click="moduleChartView = 'type'"
              />
              <q-btn
                unelevated
                dense
                :style="breakdownButtonStyle"
                :class="breakdownButtonClass"
                icon="grid_view"
                size="sm"
                @click="moduleChartView = 'breakdown'"
              />
            </div>
          </div>
        </div>
      </template>
      <div
        v-if="carbonFootprintSubtitle"
        class="text-body2 text-secondary q-px-lg q-mx-sm q-mt-xs"
      >
        {{ carbonFootprintSubtitle }}
      </div>
      <div class="q-mx-lg">
        <template v-if="moduleChartView === 'breakdown'">
          <generic-emission-tree-map-chart
            v-if="moduleTreemapData.length"
            ref="treemapChartRef"
            :key="type"
            :data="moduleTreemapData"
            :print-mode="printMode"
          />
          <chart-empty-state v-else />
        </template>
        <template v-else>
          <emission-type-breakdown-chart
            v-if="moduleCategoryRows.length"
            ref="emissionTypeChartRef"
            :key="type"
            :category-rows="moduleCategoryRows"
            :top-class-breakdown="topClassBreakdownData"
            :print-mode="printMode"
          />

          <chart-empty-state v-else />
        </template>
      </div>
      <!-- ProfessionalTravel: the PNG download sits directly under the chart
           (no divider above it); a divider then separates the trips map below,
           all within the same card. -->
      <template v-if="type === MODULES.ProfessionalTravel && !isPrintMode">
        <q-card-section class="flex justify-start q-gutter-sm q-px-lg">
          <q-btn
            unelevated
            no-caps
            outline
            icon="o_download"
            :label="$t('common_download_as_png')"
            size="xs"
            dense
            color="black"
            class="text-weight-bold q-px-sm"
            @click="downloadPNG"
          />
        </q-card-section>
        <q-separator />
        <div class="q-mx-lg q-my-lg">
          <div class="text-body1 text-weight-medium q-mb-sm text-black">
            {{ $t(`${MODULES.ProfessionalTravel}-trips-map-title-overall`) }}
          </div>
          <trips-map
            :legs="tripsMapLegs"
            :loading="moduleStore.state.loadingTripsMap"
            :aria-label="
              $t(`${MODULES.ProfessionalTravel}-trips-map-aria-label`)
            "
            testid="trips-map-overall"
          />
        </div>
      </template>
    </template>
  </q-card-section>
  <!-- ProfessionalTravel renders its own download button under the chart
       (above), so it is excluded here to avoid a duplicate. -->
  <template
    v-if="
      type !== 'headcount' &&
      type !== MODULES.ProfessionalTravel &&
      !isPrintMode
    "
  >
    <q-separator />
    <q-card-section class="flex justify-start q-gutter-sm">
      <q-btn
        unelevated
        no-caps
        outline
        icon="o_download"
        :label="$t('common_download_as_png')"
        size="xs"
        dense
        class="text-weight-bold q-px-sm"
        @click="downloadPNG"
      />
    </q-card-section>
  </template>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch, type ComputedRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { Module, MODULES } from 'src/constant/modules';
import ChartEmptyState from 'src/components/molecules/ChartEmptyState.vue';
import HeadCountBarChart from 'src/components/molecules/HeadCountBarChart.vue';
import TripsMap from 'src/components/molecules/TripsMap.vue';
import GenericEmissionTreeMapChart from 'src/components/charts/GenericEmissionTreeMapChart.vue';
import EmissionTypeBreakdownChart from 'src/components/charts/results/EmissionTypeBreakdownChart.vue';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useAuthStore } from 'src/stores/auth';
import { PermissionAction } from 'src/utils/permission';
import { usePrintMode } from 'src/composables/print/usePrintMode';
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
import { getHeadcountChartKeys } from 'src/utils/headcountChart';
import { getHeadcountMembers } from 'src/api/modules';
import { resolveTravelerNames } from 'src/utils/trips-map-data';

const props = withDefaults(
  defineProps<{
    type: Module;
    showEvolutionChart?: boolean;
    forcedView?: 'breakdown' | 'type';
    showControls?: boolean;
    printMode?: boolean;
  }>(),
  {
    showControls: true,
    forcedView: 'breakdown',
  },
);

const { t, te } = useI18n();

// Provided by ModulePage while a bulk pipeline for this module/year is
// computing emissions/aggregation.  Falls back to a constant false when
// ModuleCharts is used outside that context (results / simulation).
const statsRecalculating = inject<ComputedRef<boolean>>(
  'moduleStatsRecalculating',
  computed(() => false),
);

const moduleChartView = ref<'breakdown' | 'type'>(props.forcedView ?? 'type');

const treemapChartRef = ref<{ downloadPNG: () => Promise<void> } | null>(null);
const emissionTypeChartRef = ref<{ downloadPNG: () => Promise<void> } | null>(
  null,
);

const downloadPNG = async () => {
  if (moduleChartView.value === 'breakdown') {
    await treemapChartRef.value?.downloadPNG();
  } else {
    await emissionTypeChartRef.value?.downloadPNG();
  }
};

const isPrintMode = usePrintMode();
const showControls = computed(() => {
  if (isPrintMode.value) return false;
  return props.showControls !== false;
});

watch(
  () => props.forcedView,
  (v) => {
    if (!v) return;
    moduleChartView.value = v;
  },
);

const emissionTypeInfoKey = computed(() =>
  getEmissionTypeBreakdownInfoKey(props.type),
);

const carbonFootprintTitle = computed(() => {
  const moduleKey = `carbon_footprint_title_${props.type}`;
  if (te(moduleKey)) return t(moduleKey);
  return t('carbon_footprint_title', { module: t(props.type) });
});

const carbonFootprintSubtitle = computed(() => {
  const moduleKey = `carbon_footprint_subtitle_${props.type}`;
  if (te(moduleKey)) return t(moduleKey);
  return '';
});

const activeColor = computed(() => {
  const firstCategory = MODULE_TO_CATEGORIES.value[props.type]?.[0];
  const scale =
    CHART_CATEGORY_COLOR_SCALES.value[
      firstCategory as keyof typeof CHART_CATEGORY_COLOR_SCALES.value
    ];
  return scale?.darker ?? '#00a79f';
});

const typeButtonStyle = computed(() =>
  moduleChartView.value === 'type' ? activeButtonStyle.value : {},
);
const typeButtonClass = computed(() =>
  moduleChartView.value !== 'type' ? 'toggle-inactive' : '',
);
const breakdownButtonStyle = computed(() =>
  moduleChartView.value === 'breakdown' ? activeButtonStyle.value : {},
);
const breakdownButtonClass = computed(() =>
  moduleChartView.value !== 'breakdown' ? 'toggle-inactive' : '',
);

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
  MODULES.Equipment,
  MODULES.Purchase,
  MODULES.ResearchFacilities,
];

const moduleStore = useModuleStore();
const workspaceStore = useWorkspaceStore();
const authStore = useAuthStore();

const supportsTopClassBreakdown = computed(() =>
  TOP_CLASS_MODULES.includes(props.type),
);

function fetchTopClassBreakdownIfNeeded() {
  const unitId = workspaceStore.selectedUnit?.id;
  const year = workspaceStore.selectedYear;

  if (!authStore.hasUserModulePermission(props.type, PermissionAction.VIEW)) {
    return;
  }
  if (unitId && year && supportsTopClassBreakdown.value) {
    void moduleStore.getTopClassBreakdown(unitId, String(year), props.type);
  }
}

// SCIPER → display name for the unit's headcount roster. The trips-map API
// ships only the traveler SCIPER; we resolve names here (the same headcount
// endpoint the member table already uses) instead of on the backend.
const travelerNames = ref<Map<string, string>>(new Map());

async function loadTravelerNames(unitId: number, year: number | string) {
  try {
    const members = await getHeadcountMembers(
      unitId,
      year,
      moduleStore.carbonProjectType,
    );
    travelerNames.value = new Map(
      members.map((m) => [m.institutional_id, m.name]),
    );
  } catch (err) {
    // Non-fatal: legs simply fall back to showing the raw SCIPER.
    console.error('Failed to load headcount members for trips map', err);
  }
}

function fetchTripsMapIfNeeded() {
  const unitId = workspaceStore.selectedUnit?.id;
  const year = workspaceStore.selectedYear;
  if (unitId && year && props.type === MODULES.ProfessionalTravel) {
    void moduleStore.getProfessionalTravelTripsMap(unitId, String(year));
    void loadTravelerNames(unitId, year);
  }
}

watch(
  () => workspaceStore.selectedCarbonReport?.id,
  (carbonReportId) => {
    if (carbonReportId) {
      void moduleStore.getEmissionBreakdown(carbonReportId);
      fetchTopClassBreakdownIfNeeded();
      fetchTripsMapIfNeeded();
    }
  },
  { immediate: true },
);

watch(
  () => props.type,
  () => fetchTripsMapIfNeeded(),
);

const tripsMapLegs = computed(() =>
  resolveTravelerNames(
    moduleStore.state.tripsMap?.legs ?? [],
    travelerNames.value,
  ),
);

// Re-fetch top-class breakdown when the module type changes (e.g. navigating
// from purchases to equipment) so stale data from the previous module is replaced.
watch(
  () => props.type,
  () => fetchTopClassBreakdownIfNeeded(),
);

const headcountChartKeys = computed(() =>
  getHeadcountChartKeys(moduleStore.state.data?.stats),
);

const moduleTreemapData = computed(() => {
  const breakdown = moduleStore.state.emissionBreakdown?.module_breakdown;
  if (!breakdown || breakdown.length === 0) return [];
  const categories = MODULE_TO_CATEGORIES.value[props.type] ?? [];
  const getRowCategoryKey = (row: Record<string, unknown>): string =>
    String(
      (row as { category_key?: unknown }).category_key ?? row.category ?? '',
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
  const getRowCategoryKey = (row: Record<string, unknown>): string =>
    String(
      (row as { category_key?: unknown }).category_key ?? row.category ?? '',
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
