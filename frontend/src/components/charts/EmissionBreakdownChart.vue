<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import GenericEmissionTreeMapChart from 'src/components/charts/GenericEmissionTreeMapChart.vue';
import { MODULE_TO_CATEGORIES } from 'src/constant/charts';
import { MODULES } from 'src/constant/modules';
import {
  buildModuleTreemapData,
  CATEGORY_CHART_KEYS,
  type EmissionTreemapCategory,
} from 'src/composables/useEmissionTreemap';

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

const selectedTab = ref<TabKey | null>(null);

const activeTab = computed<TabKey | null>(() => {
  if (selectedTab.value && availableModules.value.includes(selectedTab.value)) {
    return selectedTab.value;
  }
  return availableModules.value[0] ?? null;
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

const treemapData = computed<EmissionTreemapCategory[]>(() => {
  if (!props.breakdownData || !activeTab.value) return [];

  const categories = MODULE_TO_CATEGORIES.value[activeTab.value] ?? [];
  const filteredKeys = Object.fromEntries(
    Object.entries(CATEGORY_CHART_KEYS).filter(([k]) => categories.includes(k)),
  );
  const rows = props.breakdownData.module_breakdown.map(toRow);
  return buildModuleTreemapData(rows, filteredKeys);
});
</script>

<template>
  <q-card flat bordered class="q-pa-xl">
    <div class="flex justify-between items-center q-mb-md">
      <span class="text-h5 text-weight-medium">{{
        $t('results_treemap_title')
      }}</span>
      <q-icon name="info" size="sm" color="grey-6">
        <q-tooltip>{{ $t('results_treemap_title') }}</q-tooltip>
      </q-icon>
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
        :color="activeTab === mod ? 'primary' : 'grey-7'"
        class="tab-btn"
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

    <!-- Treemap -->
    <GenericEmissionTreeMapChart
      v-if="treemapData.length > 0"
      :data="treemapData"
      :height="height ?? '250px'"
    />
    <span v-else class="text-body2 text-secondary">
      {{ $t('backoffice_reporting_chart_no_data') }}
    </span>
  </q-card>
</template>

<style scoped>
.tab-btn {
  border-radius: 6px;
}
</style>
