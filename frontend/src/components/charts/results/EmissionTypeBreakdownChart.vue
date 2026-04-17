<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import {
  getChartSubcategoryColor,
  CHART_CATEGORY_COLOR_SCALES,
} from 'src/constant/charts';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
]);

import type { EmissionBreakdownCategoryRow } from 'src/stores/modules';
import { CATEGORY_CHART_KEYS } from 'src/composables/useEmissionTreemap';
import { formatTonnesForChart } from 'src/utils/number';

const CATEGORY_LABEL_MAP: Record<string, string> = {
  process_emissions: 'charts-process-emissions-category',
  buildings_room: 'charts-buildings-room-category',
  buildings_energy_combustion: 'charts-buildings-energy-combustion-category',
  equipment: 'equipment-electric-consumption',
  external_cloud_and_ai: 'external-cloud-and-ai',
  purchases: 'purchase',
  research_facilities: 'charts-research-facilities-category',
  professional_travel: 'professional-travel',
  commuting: 'charts-commuting-category',
  food: 'charts-food-category',
  waste: 'charts-waste-category',
  embodied_energy: 'charts-embodied-energy-category',
};

const SUBCATEGORY_LABEL_MAP: Record<string, string> = {
  co2: 'charts-co2-subcategory',
  ch4: 'charts-ch4-subcategory',
  n2o: 'charts-n2o-subcategory',
  refrigerants: 'charts-refrigerants-subcategory',
  lighting: 'charts-lighting-subcategory',
  cooling: 'charts-cooling-subcategory',
  ventilation: 'charts-ventilation-subcategory',
  heating_elec: 'charts-heating-elec-subcategory',
  heating_thermal: 'charts-heating-thermal-subcategory',
  combustion: 'charts-energy-combustion-subcategory',
  natural_gas: 'charts-natural-gas-subcategory',
  heating_oil: 'charts-heating-oil-subcategory',
  biomethane: 'charts-biomethane-subcategory',
  pellets: 'charts-pellets-subcategory',
  forest_chips: 'charts-forest-chips-subcategory',
  wood_logs: 'charts-wood-logs-subcategory',
  scientific: 'charts-scientific-subcategory',
  it: 'charts-equipment-it',
  other: 'charts-other-purchases-subcategory',
  scientific_equipment: 'charts-scientific-subcategory',
  it_equipment: 'charts-equipment-it',
  consumable_accessories: 'charts-consumables-subcategory',
  biological_chemical_gaseous: 'charts-bio-chemicals-subcategory',
  services: 'charts-services-subcategory',
  vehicles: 'charts-other-purchases-subcategory',
  additional: 'charts-other-purchases-subcategory',
  goods_and_services: 'charts-services-subcategory',
  plane: 'charts-plane-subcategory',
  train: 'charts-train-subcategory',
  clouds: 'charts-clouds-subcategory',
  ai: 'charts-ai-subcategory',
  provider: 'charts-ai-provider-subcategory',
  ai_provider: 'charts-ai-provider-subcategory',
  provider_google: 'charts-ai-provider-google-subcategory',
  provider_openai: 'charts-ai-provider-openai-subcategory',
  provider_anthropic: 'charts-ai-provider-anthropic-subcategory',
  provider_mistral_ai: 'charts-ai-provider-mistral-ai-subcategory',
  provider_cohere: 'charts-ai-provider-cohere-subcategory',
  provider_others: 'charts-ai-provider-others-subcategory',
  stockage: 'charts-stockage-subcategory',
  virtualisation: 'charts-virtualisation-subcategory',
  calcul: 'charts-calcul-subcategory',
  facilities: 'charts-research-facilities-subcategory',
  animal: 'charts-research-animal-subcategory',
  rest: 'charts-rest-subcategory',
  'new-env': 'charts-new-env-subcategory',
  'new-tech': 'charts-new-tech-subcategory',
  'ren-env': 'charts-ren-env-subcategory',
  'ren-tech': 'charts-ren-tech-subcategory',
  demolition: 'charts-demolition-subcategory',
};

export interface TopClassBreakdownItem {
  name: string;
  value: number;
  children: Array<{ name: string; value: number }>;
}

const props = defineProps<{
  categoryRows: EmissionBreakdownCategoryRow[];
  topClassBreakdown?: TopClassBreakdownItem[];
}>();

const { t } = useI18n();

const categoryKeyPrefixes = Object.keys(CATEGORY_LABEL_MAP);

/**
 * Build the horizontal bar chart data from the category rows.
 *
 * Bars = XX categories (parent_key groups, or leaf keys if no parent_key)
 * Segments = YY subcategories within each XX bar
 *
 * When `topClassBreakdown` is provided, each subcategory becomes a bar
 * with segments for the top N items + "rest".
 */
// Maps compound segment keys → display labels (used in top-class mode)
const segmentLabelOverrides = new Map<string, string>();

/**
 * Sort bars within each category by the CATEGORY_CHART_KEYS display order.
 * Shared by the default and top-class breakdown branches so both produce
 * a deterministic, visually intended order rather than backend/DB iteration order.
 */
function sortBarsByDisplayOrder(
  bars: Record<string, unknown>[],
  barCategoryMap: Map<string, string>,
  barLabelMap: Map<string, string>,
): void {
  bars.sort((a, b) => {
    const aCat = barCategoryMap.get(a.xx_category as string) ?? '';
    const bCat = barCategoryMap.get(b.xx_category as string) ?? '';
    if (aCat !== bCat) return 0; // preserve cross-category order
    const keys = CATEGORY_CHART_KEYS[aCat] ?? [];
    const aIdx = keys.indexOf(barLabelMap.get(a.xx_category as string) ?? '');
    const bIdx = keys.indexOf(barLabelMap.get(b.xx_category as string) ?? '');
    return (aIdx === -1 ? 999 : aIdx) - (bIdx === -1 ? 999 : bIdx);
  });
}

const chartData = computed(() => {
  const emptyResult = {
    bars: [] as Record<string, unknown>[],
    segmentKeys: [] as string[],
    barKey: 'xx_category',
    barCategoryMap: new Map<string, string>(),
    barLabelMap: new Map<string, string>(),
  };

  segmentLabelOverrides.clear();

  // --- Top-class breakdown mode ---
  if (props.topClassBreakdown?.length) {
    const categoryKey = props.categoryRows[0]?.category_key ?? '';
    const bars: Record<string, unknown>[] = [];
    const segmentKeysSet = new Set<string>();
    const barCategoryMap = new Map<string, string>();
    const barLabelMap = new Map<string, string>();
    let segCounter = 0;

    for (const subcategory of props.topClassBreakdown) {
      const compoundKey = `${categoryKey}_${subcategory.name}`;
      const barData: Record<string, unknown> = { xx_category: compoundKey };
      barCategoryMap.set(compoundKey, categoryKey);
      barLabelMap.set(compoundKey, subcategory.name);

      for (const child of subcategory.children) {
        // Use a numeric suffix to guarantee unique, parseable segment keys
        const segKey = `_tcb_${segCounter++}`;
        segmentKeysSet.add(segKey);
        segmentLabelOverrides.set(segKey, child.name);
        barData[segKey] = child.value / 1000.0; // kg → tonnes
      }
      bars.push(barData);
    }

    sortBarsByDisplayOrder(bars, barCategoryMap, barLabelMap);

    return {
      bars,
      segmentKeys: Array.from(segmentKeysSet),
      barKey: 'xx_category',
      barCategoryMap,
      barLabelMap,
    };
  }

  // --- Default mode ---
  if (!props.categoryRows.length) return emptyResult;

  // Group emissions by (category_key, parent_key/key) to keep each category's bars distinct.
  // The compound key `catKey_barName` prevents cross-category name collisions (e.g. heating_thermal).
  const barMap = new Map<string, Record<string, number>>();
  const barCategoryMap = new Map<string, string>(); // compoundKey → categoryKey
  const barLabelMap = new Map<string, string>(); // compoundKey → display barName

  for (const row of props.categoryRows) {
    for (const emission of row.emissions) {
      const value = Number(emission.value) || 0;
      if (value <= 0) continue;

      const barName = emission.parent_key ?? emission.key;
      const collapseAiChildren =
        row.category_key === 'external_cloud_and_ai' && barName === 'ai';
      const segmentKey = collapseAiChildren ? barName : emission.key;
      const compoundKey = `${row.category_key}_${barName}`;

      if (!barMap.has(compoundKey)) {
        barMap.set(compoundKey, {});
        barCategoryMap.set(compoundKey, row.category_key);
        barLabelMap.set(compoundKey, barName);
      }
      const bar = barMap.get(compoundKey)!;
      // Segment keys must also be unique per compound key to avoid collisions across categories
      const compoundSegment = `${row.category_key}_${segmentKey}`;
      bar[compoundSegment] = (bar[compoundSegment] ?? 0) + value;
    }
  }

  // Collect all unique segment keys
  const segmentKeysSet = new Set<string>();
  const bars: Record<string, unknown>[] = [];

  for (const [compoundKey, segments] of barMap) {
    const barData: Record<string, unknown> = { xx_category: compoundKey };
    for (const [key, val] of Object.entries(segments)) {
      segmentKeysSet.add(key);
      barData[key] = val;
    }
    bars.push(barData);
  }

  sortBarsByDisplayOrder(bars, barCategoryMap, barLabelMap);

  return {
    bars,
    segmentKeys: Array.from(segmentKeysSet),
    barKey: 'xx_category',
    barCategoryMap,
    barLabelMap,
  };
});

function translateSubcategory(key: string): string {
  // Top-class mode uses numeric segment keys with label overrides
  const override = segmentLabelOverrides.get(key);
  if (override) {
    const i18nKey = SUBCATEGORY_LABEL_MAP[override];
    return i18nKey ? t(i18nKey) : override;
  }

  // `key` is a dataset dimension name. To keep segment dimensions unique across
  // categories we build it as `${categoryKey}_${subcategoryKey}` (e.g. `process_emissions_co2`).
  // The i18n map only contains `subcategoryKey` (e.g. `co2`), so we strip the category prefix.
  const directI18nKey = SUBCATEGORY_LABEL_MAP[key];
  if (directI18nKey) return t(directI18nKey);

  const categoryPrefix = categoryKeyPrefixes.find((catKey) =>
    key.startsWith(`${catKey}_`),
  );
  if (!categoryPrefix) return key;

  const subcategoryKey = key.slice(categoryPrefix.length + 1);
  const i18nKey = SUBCATEGORY_LABEL_MAP[subcategoryKey];
  return i18nKey ? t(i18nKey) : subcategoryKey;
}

function translateBar(barName: string): string {
  // Try subcategory label first, then category label
  const subKey = SUBCATEGORY_LABEL_MAP[barName];
  if (subKey) return t(subKey);
  const catKey = CATEGORY_LABEL_MAP[barName];
  if (catKey) return t(catKey);
  return barName;
}

const shadeOrder = ['darker', 'dark', 'default', 'light', 'lighter'] as const;

// Track index per category so each bar within a category gets a distinct shade
const segmentColorMap = computed(() => {
  const map: Record<string, string> = {};
  const { bars, barCategoryMap, barLabelMap } = chartData.value;
  const categoryBarIndex = new Map<string, number>();

  bars.forEach((bar) => {
    const compoundKey = bar.xx_category as string;
    const catKey = barCategoryMap.get(compoundKey) ?? '';
    const barName = barLabelMap.get(compoundKey) ?? compoundKey;
    const barIndex = categoryBarIndex.get(catKey) ?? 0;
    categoryBarIndex.set(catKey, barIndex + 1);

    const scale = CHART_CATEGORY_COLOR_SCALES.value[catKey];
    const specificBarColor = getChartSubcategoryColor(catKey, barName, '');
    const barColor =
      specificBarColor ||
      (scale ? scale[shadeOrder[barIndex % shadeOrder.length]] : '#999999');

    for (const [key, val] of Object.entries(bar)) {
      if (key === 'xx_category') continue;
      if (typeof val === 'number' && val > 0) {
        map[key] = barColor;
      }
    }
  });

  return map;
});

function getSegmentColor(segmentKey: string): string {
  return segmentColorMap.value[segmentKey] ?? '#999999';
}

const chartOption = computed((): EChartsOption => {
  const { bars, segmentKeys, barKey, barLabelMap } = chartData.value;

  if (!bars.length) return {};

  const source = bars.map((bar) => ({
    ...bar,
    [barKey]: translateBar(
      barLabelMap.get(bar[barKey] as string) ?? (bar[barKey] as string),
    ),
  }));

  const series = segmentKeys.map((key) => ({
    name: translateSubcategory(key),
    type: 'bar' as const,
    stack: 'total',
    encode: {
      y: barKey,
      x: key,
    },
    itemStyle: {
      color: getSegmentColor(key),
      borderColor: '#fff',
      borderWidth: 1,
    },
    // Between IT Focus (32px) and default auto width (often very thick)
    barWidth: 60,
    label: { show: false },
    emphasis: {
      focus: 'series' as const,
      blurScope: 'coordinateSystem' as const,
    },
    blur: { itemStyle: { opacity: 0.4 } },
  }));

  return {
    animation: false,
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as {
          seriesName?: string;
          marker?: string;
          seriesIndex?: number;
          data?: Record<string, unknown>;
        };
        const dimKey = segmentKeys[p.seriesIndex ?? 0];
        const row = p.data;
        const val = row && dimKey !== undefined ? Number(row[dimKey]) || 0 : 0;
        if (val <= 0) return '';
        return `${p.marker || ''} <strong>${p.seriesName || ''}</strong>: ${formatTonnesForChart(val)}${t('results_units_tonnes')}`;
      },
    },
    legend: { show: false },
    grid: {
      left: '3%',
      right: '4%',
      top: 10,
      bottom: 40,
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      name: t('tco2eq'),
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { fontSize: 11, fontWeight: 'bold' },
      axisLabel: { formatter: '{value}' },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      axisLabel: {
        fontSize: 10,
        width: 150,
        overflow: 'truncate',
      },
    },
    dataset: {
      dimensions: [barKey, ...segmentKeys],
      source: source as Array<Record<string, unknown>>,
    },
    series: series as echarts.SeriesOption[],
  };
});

const chartHeight = computed(() => {
  const barCount = chartData.value.bars.length;
  return Math.max(200, barCount * 60 + 60);
});
</script>

<template>
  <q-card flat class="container container--pa-none q-mb-md">
    <q-card-section class="flex justify-center items-center">
      <v-chart
        v-if="chartData.bars.length"
        class="chart"
        autoresize
        :option="chartOption"
        :style="{ height: chartHeight + 'px' }"
      />
      <span v-else class="text-body2 text-secondary">
        {{ $t('no-chart-data') }}
      </span>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.chart {
  width: 100%;
  min-height: 200px;
}
</style>
