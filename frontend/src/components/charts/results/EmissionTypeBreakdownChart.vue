<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption, SeriesOption } from 'echarts';
import {
  buildChartDecal,
  getChartSubcategoryColor,
  CHART_CATEGORY_COLOR_SCALES,
  RESULTS_CATEGORY_LABEL_KEYS,
} from 'src/constant/charts';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  AriaComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';
import TooltipEcharts from './TooltipEcharts.vue';
import { useEchartsTooltip } from './useEchartsTooltip';
import { useColorblindStore } from 'src/stores/colorblind';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  AriaComponent,
]);

import type { EmissionBreakdownCategoryRow } from 'src/stores/modules';
import {
  CATEGORY_CHART_KEYS,
  normalizeParentKey,
} from 'src/composables/useEmissionTreemap';
import { formatTonnesForChart } from 'src/utils/number';
import { usePrintMode } from 'src/composables/print/usePrintMode';
import { downloadEchartAsPng } from 'src/utils/chartDownload';

const CATEGORY_LABEL_MAP: Record<string, string> = RESULTS_CATEGORY_LABEL_KEYS;

const SUBCATEGORY_LABEL_MAP: Record<string, string> = {
  co2: 'process-emissions.category.co2',
  ch4: 'process-emissions.category.ch4',
  n2o: 'process-emissions.category.n2o',
  refrigerants: 'process-emissions.category.refrigerant',
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
  other: 'charts-other-equipment-subcategory',
  scientific_equipment: 'charts-scientific-subcategory',
  it_equipment: 'charts-equipment-it',
  consumable_accessories: 'charts-consumables-subcategory',
  biological_chemical_gaseous: 'charts-bio-chemicals-subcategory',
  services: 'charts-services-subcategory',
  vehicles: 'charts-vehicles-subcategory',
  additional: 'charts-additional-purchases-subcategory',
  other_purchases: 'charts-other-purchases-subcategory',
  goods_and_services: 'charts-services-subcategory',
  plane: 'charts-plane-subcategory',
  train: 'charts-train-subcategory',
  class_1: 'charts-class-1-subcategory',
  class_2: 'charts-class-2-subcategory',
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
  it_facilities: 'charts-research-it-facilities-subcategory',
  animal: 'charts-research-animal-subcategory',
  mice_and_fish_animal_facilities: 'charts-research-animal-subcategory',
  mice: 'charts-animal-mice-subcategory',
  fish: 'charts-animal-fish-subcategory',
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
  children: Array<{ name: string; value: number; translation_key?: string }>;
}

const props = defineProps<{
  categoryRows: EmissionBreakdownCategoryRow[];
  topClassBreakdown?: TopClassBreakdownItem[];
  printMode?: boolean;
}>();

const { t, te } = useI18n();
const isPrintMode = usePrintMode();
const colorblindStore = useColorblindStore();

const categoryKeyPrefixes = Object.keys(CATEGORY_LABEL_MAP);

// Defines left-to-right stacking order for room-type segments within each buildings bar.
const ROOM_TYPE_SEGMENT_ORDER = [
  'laboratories',
  'office',
  'archives',
  'libraries',
  'auditoriums',
  'miscellaneous',
];

function sortSegmentKeys(keys: string[]): string[] {
  return keys.slice().sort((a, b) => {
    const aSuffix = a.split('_').pop() ?? a;
    const bSuffix = b.split('_').pop() ?? b;
    const aIdx = ROOM_TYPE_SEGMENT_ORDER.indexOf(aSuffix);
    const bIdx = ROOM_TYPE_SEGMENT_ORDER.indexOf(bSuffix);
    if (aIdx === -1 && bIdx === -1) return 0;
    if (aIdx === -1) return 1;
    if (bIdx === -1) return -1;
    return aIdx - bIdx;
  });
}

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

function getRowCategoryKey(row: EmissionBreakdownCategoryRow): string {
  // Some endpoints return only `category` and omit `category_key`.
  return String(row.category_key ?? row.category ?? '');
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
    const categoryKey = props.categoryRows[0]
      ? getRowCategoryKey(props.categoryRows[0])
      : '';
    const bars: Record<string, unknown>[] = [];
    const segmentKeysSet = new Set<string>();
    const barCategoryMap = new Map<string, string>();
    const barLabelMap = new Map<string, string>();
    let segCounter = 0;

    for (const subcategory of props.topClassBreakdown) {
      const normalizedName = normalizeParentKey(categoryKey, subcategory.name);
      const compoundKey = `${categoryKey}_${subcategory.name}`;
      const barData: Record<string, unknown> = { xx_category: compoundKey };
      barCategoryMap.set(compoundKey, categoryKey);
      barLabelMap.set(compoundKey, normalizedName);

      const sortedChildren = [...subcategory.children].sort((a, b) => {
        if (a.name === 'rest') return 1;
        if (b.name === 'rest') return -1;
        return b.value - a.value;
      });
      for (const child of sortedChildren) {
        // Use a numeric suffix to guarantee unique, parseable segment keys
        const segKey = `_tcb_${segCounter++}`;
        segmentKeysSet.add(segKey);
        // Prefer translation_key (i18n key from Factor table) over raw name
        segmentLabelOverrides.set(segKey, child.translation_key ?? child.name);
        barData[segKey] = child.value / 1000.0; // kg → tonnes
      }
      bars.push(barData);
    }

    sortBarsByDisplayOrder(bars, barCategoryMap, barLabelMap);

    return {
      bars,
      segmentKeys: sortSegmentKeys(Array.from(segmentKeysSet)),
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
    const categoryKey = getRowCategoryKey(row);
    if (!categoryKey) continue;
    const allowedParents = CATEGORY_CHART_KEYS[categoryKey] ?? [];
    for (const emission of row.emissions) {
      const value = Number(emission.value) || 0;
      if (value <= 0) continue;

      const rawBarName = emission.parent_key ?? emission.key;
      const barName = normalizeParentKey(categoryKey, String(rawBarName));
      if (allowedParents.length > 0 && !allowedParents.includes(barName)) {
        continue;
      }
      const collapseAiChildren =
        categoryKey === 'external_cloud_and_ai' && barName === 'ai';
      const segmentKey = collapseAiChildren ? barName : emission.key;
      const compoundKey = `${categoryKey}_${barName}`;

      if (!barMap.has(compoundKey)) {
        barMap.set(compoundKey, {});
        barCategoryMap.set(compoundKey, categoryKey);
        barLabelMap.set(compoundKey, barName);
      }
      const bar = barMap.get(compoundKey)!;
      // Segment keys must also be unique per compound key to avoid collisions across categories
      const compoundSegment = `${categoryKey}_${segmentKey}`;
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
    segmentKeys: sortSegmentKeys(Array.from(segmentKeysSet)),
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
    if (i18nKey) return t(i18nKey);
    return te(override) ? t(override) : override;
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
  if (i18nKey) return t(i18nKey);
  return te(subcategoryKey) ? t(subcategoryKey) : subcategoryKey;
}

function translateBar(categoryKey: string, barName: string): string {
  const baseName =
    String(barName ?? '').split('__')[0] ?? String(barName ?? '');
  const subKey = SUBCATEGORY_LABEL_MAP[baseName];
  if (subKey) return t(subKey);
  const catKey = CATEGORY_LABEL_MAP[baseName];
  if (catKey) return t(catKey);
  return baseName || barName;
}

const shadeOrder = ['darker', 'dark', 'default', 'light', 'lighter'] as const;

// Maps bar compound key → its designated color.
// Using a per-bar map (rather than per-segment) ensures each bar row gets its
// own distinct shade even when multiple bars share the same segment keys
// (e.g. buildings_room subcategories all share room-type segment keys).
const barColorMap = computed(() => {
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
    map[compoundKey] =
      specificBarColor ||
      (scale ? scale[shadeOrder[barIndex % shadeOrder.length]] : '#999999');
  });

  return map;
});

function getBarColor(dataIndex: number): string {
  const bar = chartData.value.bars[dataIndex];
  if (!bar) return '#999999';
  return barColorMap.value[bar.xx_category as string] ?? '#999999';
}

const chartOption = computed((): EChartsOption => {
  const { bars, segmentKeys, barKey, barLabelMap } = chartData.value;

  if (!bars.length) return {};

  const source = bars.map((bar) => ({
    ...bar,
    [barKey]: (() => {
      const compoundKey = bar[barKey] as string;
      const categoryKey = chartData.value.barCategoryMap.get(compoundKey) ?? '';
      const rawBarName =
        barLabelMap.get(compoundKey) ?? (bar[barKey] as string);
      return translateBar(categoryKey, rawBarName);
    })(),
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
      color: (params: unknown) =>
        getBarColor((params as { dataIndex: number }).dataIndex),
      borderColor: '#fff',
      borderWidth: 1,
    },
    // Between IT Focus (32px) and default auto width (often very thick)
    barWidth: 58,
    label: { show: false },
    emphasis: { disabled: true },
  }));

  return {
    animation: false,
    aria: {
      enabled: true,
      decal: buildChartDecal(colorblindStore.enabled),
    },
    tooltip: isPrintMode.value
      ? { show: false }
      : {
          trigger: 'item',
          formatter: (params: unknown) => {
            const p = params as {
              seriesName?: string;
              color?: string;
              seriesIndex?: number;
              data?: Record<string, unknown>;
            };
            const dimKey = segmentKeys[p.seriesIndex ?? 0];
            const row = p.data;
            const val =
              row && dimKey !== undefined ? Number(row[dimKey]) || 0 : 0;
            if (val <= 0) {
              emitTooltip(null);
              return '';
            }
            emitTooltip({
              rows: [
                {
                  label: p.seriesName ?? '',
                  value: `${formatTonnesForChart(val)}${t('results_units_tonnes')}`,
                  color: p.color ?? '#888',
                },
              ],
            });
            return '';
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
    series: series as SeriesOption[],
  };
});

const chartHeight = computed(() => {
  const barCount = chartData.value.bars.length;
  const natural = Math.max(200, barCount * 60 + 60);
  return isPrintMode.value ? Math.min(natural, 500) : natural;
});

const chartRef = ref<InstanceType<typeof VChart>>();
const { tooltip, style, attach, emitTooltip } = useEchartsTooltip();

const onChartReady = async () => {
  await nextTick();
  const chart = chartRef.value?.chart;
  if (!chart) return;
  attach(chart);
};

const downloadPNG = () =>
  downloadEchartAsPng(chartRef.value?.chart, 'emission-breakdown');

defineExpose({ downloadPNG });
</script>

<template>
  <div class="q-mb-md">
    <div class="flex justify-center items-center">
      <v-chart
        v-if="chartData.bars.length"
        ref="chartRef"
        :key="colorblindStore.enabled ? 'cb' : 'default'"
        class="chart"
        autoresize
        :option="chartOption"
        :style="{ height: chartHeight + 'px' }"
        @vue:mounted="onChartReady"
      />
      <span v-else class="text-body2 text-secondary">
        {{ $t('no-chart-data') }}
      </span>
    </div>
    <Teleport to="body">
      <tooltip-echarts
        v-if="tooltip.visible"
        :tooltip-state="tooltip.data"
        :style="style"
      />
    </Teleport>
  </div>
</template>

<style scoped>
.chart {
  width: 100%;
  min-height: 200px;
}
</style>
