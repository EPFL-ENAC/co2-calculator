<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import GenericEmissionTreeMapChart from 'src/components/charts/GenericEmissionTreeMapChart.vue';
import EmissionTypeBreakdownChart from 'src/components/charts/results/EmissionTypeBreakdownChart.vue';
import {
  MODULE_TO_CATEGORIES,
  CHART_CATEGORY_COLOR_SCALES,
} from 'src/constant/charts';
import { getEmissionTypeBreakdownInfoKey } from 'src/constant/emissionTypeBreakdownInfo';
import { MODULES } from 'src/constant/modules';
import {
  buildModuleTreemapData,
  CATEGORY_CHART_KEYS,
  type EmissionTreemapCategory,
} from 'src/composables/useEmissionTreemap';
import type { EmissionBreakdownCategoryRow } from 'src/stores/modules';

interface BreakdownData {
  module_breakdown: Array<Record<string, unknown>>;
}

const props = defineProps<{
  breakdownData: BreakdownData | null;
  height?: string;
}>();

const { t } = useI18n();

// Modules that can appear as tabs (exclude headcount — no treemap chart)
// Same left-to-right order as the bar chart (mirrors backend MODULE_BREAKDOWN_ORDER)
const TREEMAP_MODULES = [
  MODULES.ProcessEmissions,
  MODULES.Buildings,
  MODULES.EquipmentElectricConsumption,
  MODULES.ExternalCloudAndAI,
  MODULES.Purchase,
  MODULES.ResearchFacilities,
  MODULES.ProfessionalTravel,
] as const;

/** Modules that actually have non-zero data in the current breakdown */
const availableModules = computed(() => {
  if (!props.breakdownData) return [];
  const rows = props.breakdownData.module_breakdown;
  return TREEMAP_MODULES.filter((mod) => {
    const categories = MODULE_TO_CATEGORIES.value[mod] ?? [];
    return categories.some((cat) => {
      const row = rows.find((r) => r.category === cat);
      if (!row) return false;
      return Object.entries(row).some(
        ([k, v]) => k !== 'category' && !k.endsWith('StdDev') && Number(v) > 0,
      );
    });
  });
});

type TabKey = (typeof TREEMAP_MODULES)[number];

const chartView = ref<'breakdown' | 'type'>('breakdown');

const selectedTab = ref<TabKey | null>(null);

const activeTab = computed<TabKey | null>(() => {
  if (selectedTab.value && availableModules.value.includes(selectedTab.value)) {
    return selectedTab.value;
  }
  return availableModules.value[0] ?? null;
});

const activeColor = computed(() => {
  const firstCategory = MODULE_TO_CATEGORIES.value[activeTab.value ?? '']?.[0];
  const scale =
    CHART_CATEGORY_COLOR_SCALES.value[
      firstCategory as keyof typeof CHART_CATEGORY_COLOR_SCALES.value
    ];
  return scale?.darker ?? '#00a79f';
});

function selectTab(tab: TabKey) {
  selectedTab.value = tab;
}

type BreakdownRow = { category: string; [key: string]: number | string };

function toRow(r: Record<string, unknown>): BreakdownRow {
  const row: BreakdownRow = { category: String(r.category ?? '') };
  for (const [k, v] of Object.entries(r)) {
    if (k === 'category') continue;
    if (typeof v === 'number' || typeof v === 'string') row[k] = v;
  }
  return row;
}

const categoryRows = computed<EmissionBreakdownCategoryRow[]>(() => {
  if (!props.breakdownData || !activeTab.value) return [];
  const categories = MODULE_TO_CATEGORIES.value[activeTab.value] ?? [];
  const rows = props.breakdownData.module_breakdown.filter((row) =>
    categories.includes(String(row.category ?? '')),
  ) as EmissionBreakdownCategoryRow[];

  return rows.map((row) => {
    const allowedBarNames = new Set(
      CATEGORY_CHART_KEYS[row.category_key] ?? [],
    );
    const isFilterApplicable = row.emissions.some((e) =>
      allowedBarNames.has((e.parent_key ?? e.key) as string),
    );
    if (!isFilterApplicable) return row;
    return {
      ...row,
      emissions: row.emissions.filter((e) =>
        allowedBarNames.has((e.parent_key ?? e.key) as string),
      ),
    };
  });
});

const treemapData = computed<EmissionTreemapCategory[]>(() => {
  if (!props.breakdownData || !activeTab.value) return [];

  const categories = MODULE_TO_CATEGORIES.value[activeTab.value] ?? [];
  const filteredKeys = Object.fromEntries(
    Object.entries(CATEGORY_CHART_KEYS).filter(([k]) => categories.includes(k)),
  );
  const rows = props.breakdownData.module_breakdown.map(toRow);
  return buildModuleTreemapData(rows, filteredKeys);
});

const emissionTypeInfoKey = computed(() =>
  getEmissionTypeBreakdownInfoKey(activeTab.value),
);
</script>

<template>
  <q-card flat bordered class="q-pa-xl">
    <div class="flex justify-between items-center q-mb-md">
      <span class="text-h5 text-weight-medium">{{
        $t('results_treemap_title')
      }}</span>
      <div class="flex items-center no-wrap q-gutter-xs">
        <q-btn
          v-if="emissionTypeInfoKey && chartView === 'type'"
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
            :style="
              chartView === 'type'
                ? { backgroundColor: activeColor, color: '#fff' }
                : {}
            "
            :class="chartView !== 'type' ? 'toggle-inactive' : ''"
            icon="stacked_bar_chart"
            size="sm"
            @click="chartView = 'type'"
          />
          <q-btn
            unelevated
            dense
            :style="
              chartView === 'breakdown'
                ? { backgroundColor: activeColor, color: '#fff' }
                : {}
            "
            :class="chartView !== 'breakdown' ? 'toggle-inactive' : ''"
            icon="grid_view"
            size="sm"
            @click="chartView = 'breakdown'"
          />
        </div>
      </div>
    </div>

    <!-- Module tab buttons -->
    <div class="flex flex-wrap q-gutter-sm q-mb-md">
      <q-btn
        v-for="mod in availableModules"
        :key="mod"
        :outline="activeTab !== mod"
        :unelevated="activeTab === mod"
        no-caps
        size="sm"
        color="primary"
        class="tab-btn text-weight-medium"
        @click="selectTab(mod)"
      >
        <ModuleIcon
          :name="mod"
          size="sm"
          :color="activeTab === mod ? 'white' : 'accent'"
          class="q-mr-xs"
        />
        {{ t(mod) }}
      </q-btn>
    </div>

    <template v-if="chartView === 'breakdown'">
      <GenericEmissionTreeMapChart
        v-if="treemapData.length > 0"
        :data="treemapData"
        :height="height ?? '250px'"
      />
      <span v-else class="text-body2 text-secondary">
        {{ $t('backoffice_reporting_chart_no_data') }}
      </span>
    </template>
    <template v-else>
      <EmissionTypeBreakdownChart
        v-if="categoryRows.length"
        :category-rows="categoryRows"
        class="full-width"
      />
      <span v-else class="text-body2 text-secondary">
        {{ $t('backoffice_reporting_chart_no_data') }}
      </span>
    </template>
  </q-card>
</template>

<style scoped>
.tab-btn {
  border-radius: 3px;
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
