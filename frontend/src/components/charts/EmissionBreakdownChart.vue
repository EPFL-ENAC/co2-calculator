<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import GenericEmissionTreeMapChart from 'src/components/charts/GenericEmissionTreeMapChart.vue';
import EmissionTypeBreakdownChart from 'src/components/charts/results/EmissionTypeBreakdownChart.vue';
import {
  MODULE_TO_CATEGORIES,
  CHART_CATEGORY_COLOR_SCALES,
  CHART_CATEGORY_COLOR_SCHEMES,
  CHART_SUBCATEGORY_COLOR_SCHEMES,
} from 'src/constant/charts';
import { getEmissionTypeBreakdownInfoKey } from 'src/constant/emissionTypeBreakdownInfo';
import { MODULES } from 'src/constant/modules';
import {
  CATEGORY_CHART_KEYS,
  type EmissionTreemapCategory,
  type EmissionTreemapChild,
} from 'src/composables/useEmissionTreemap';
import type {
  EmissionBreakdownCategoryRow,
  EmissionBreakdownValue,
} from 'src/stores/modules';

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

  const catColorSchemes = CHART_CATEGORY_COLOR_SCHEMES.value as Record<
    string,
    string
  >;
  const subColorSchemes = CHART_SUBCATEGORY_COLOR_SCHEMES.value as Record<
    string,
    Record<string, string>
  >;

  const categories = MODULE_TO_CATEGORIES.value[activeTab.value] ?? [];
  // Read directly from raw module_breakdown to get every leaf emission
  // without the categoryRows allowedBarNames filter stripping them out.
  const moduleRows = props.breakdownData
    .module_breakdown as EmissionBreakdownCategoryRow[];

  const result: EmissionTreemapCategory[] = [];

  for (const rawRow of moduleRows) {
    const cat = String(rawRow.category_key || rawRow.category || '');
    if (!categories.includes(cat) || !(cat in CATEGORY_CHART_KEYS)) continue;

    const catColor = catColorSchemes[cat] ?? '#999999';
    const subColors = subColorSchemes[cat] ?? {};
    const catKeys = CATEGORY_CHART_KEYS[cat] ?? [];
    const rawEmissions = (rawRow.emissions as EmissionBreakdownValue[]) ?? [];

    // Group leaf emissions by their parent subcategory key.
    // Use explicit parent_key when present so that leaf items like
    // {key:'eco', parent_key:'plane'} are grouped under 'plane', not 'eco'.
    const byParent = new Map<string, EmissionBreakdownValue[]>();
    for (const emission of rawEmissions) {
      const parentKey = emission.parent_key
        ? String(emission.parent_key)
        : String(emission.key);
      if (!catKeys.includes(parentKey)) continue;
      if (!byParent.has(parentKey)) byParent.set(parentKey, []);
      byParent.get(parentKey)!.push(emission);
    }

    const children: EmissionTreemapChild[] = [];
    let catTotal = 0;

    // Emit leaves in CATEGORY_CHART_KEYS parent order
    for (const parentKey of catKeys) {
      const emissions = byParent.get(parentKey) ?? [];
      const parentColor = subColors[parentKey] ?? catColor;
      for (const emission of emissions) {
        const val = Number(emission.value) || 0;
        if (val <= 0) continue;
        children.push({
          name: emission.key,
          value: val,
          percentage: 0,
          color: parentColor,
        });
        catTotal += val;
      }
    }

    if (catTotal <= 0 || children.length === 0) continue;

    children.forEach((c) => {
      c.percentage = (c.value / catTotal) * 100;
    });

    result.push({
      name: cat,
      value: catTotal,
      percentage: 0,
      color: catColor,
      children,
    });
  }

  const grandTotal = result.reduce((s, c) => s + c.value, 0);
  result.forEach((cat) => {
    cat.percentage = grandTotal > 0 ? (cat.value / grandTotal) * 100 : 0;
  });

  return result;
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
