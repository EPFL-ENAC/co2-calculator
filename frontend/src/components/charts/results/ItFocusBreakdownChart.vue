<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { ScatterChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import {
  TooltipComponent,
  GridComponent,
  AriaComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';

import TooltipEcharts from 'src/components/charts/results/TooltipEcharts.vue';
import { useEchartsTooltip } from 'src/components/charts/results/useEchartsTooltip';
import {
  buildChartDecal,
  CHART_CATEGORY_COLOR_SCHEMES,
  colors,
} from 'src/constant/charts';
import { IT_FOCUS_CATEGORY_TO_MODULE } from 'src/constant/itFocus';
import { useColorblindStore } from 'src/stores/colorblind';
import { downloadEchartAsPng } from 'src/utils/chartDownload';
import type { ItBreakdownResponse } from 'src/stores/modules';
import type { TooltipRow, TooltipState } from 'src/types/chartTooltip';

use([
  CanvasRenderer,
  ScatterChart,
  TooltipComponent,
  GridComponent,
  AriaComponent,
]);

const props = withDefaults(
  defineProps<{
    data: ItBreakdownResponse;
    printMode?: boolean;
    compact?: boolean;
  }>(),
  {
    printMode: false,
    compact: false,
  },
);

const { t } = useI18n();
const colorblindStore = useColorblindStore();

const { tooltip, style, attach, emitTooltip } = useEchartsTooltip();
const chartRef = ref<InstanceType<typeof VChart>>();

function buildWaffleTooltipStateFromLabel(label: string): TooltipState {
  const cat = waffleCategoryData.value.find((c) => c.label === label);
  if (!cat) return null;

  const rows: TooltipRow[] = [
    {
      label: cat.label,
      value: waffleUnitsToPercentLabel(cat.units),
      color: cat.color,
      icon: cat.isIT
        ? (IT_FOCUS_CATEGORY_TO_MODULE[cat.key] ?? undefined)
        : undefined,
    },
  ];

  return { rows };
}

const onChartReady = async () => {
  await nextTick();
  const chart = chartRef.value?.chart;
  if (!chart) return;
  attach(chart);

  chart.on('mousemove', (p: unknown) => {
    const params = p as { seriesName?: unknown; name?: unknown } | null;
    const label = String(params?.seriesName ?? params?.name ?? '');
    emitTooltip(buildWaffleTooltipStateFromLabel(label));
  });
  chart.on('mouseout', () => emitTooltip(null));
};

const waffleContainerRef = ref<HTMLElement | null>(null);
const waffleWidth = ref(0);
let resizeObserver: ResizeObserver | null = null;

function setupWaffleResizeObserver(el: HTMLElement): void {
  resizeObserver?.disconnect();
  const measure = () => {
    waffleWidth.value = el.getBoundingClientRect().width;
  };
  resizeObserver = new ResizeObserver((entries) => {
    waffleWidth.value = entries[0].contentRect.width;
  });
  resizeObserver.observe(el);
  measure();
  requestAnimationFrame(measure);
}

onMounted(() => {
  if (waffleContainerRef.value)
    setupWaffleResizeObserver(waffleContainerRef.value);
});

watch(
  waffleContainerRef,
  async (el) => {
    if (!el) return;
    await nextTick();
    setupWaffleResizeObserver(el);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
});

const CATEGORY_LABEL_MAP: Record<string, string> = {
  equipment_it: 'it-focus-equipment-it',
  purchases_it: 'it-focus-purchases-it',
  external_cloud_and_ai: 'it-focus-cloud-ai',
  research_facilities_it: 'it-focus-research-facilities',
};

const IT_FOCUS_CATEGORY_ORDER = [
  'equipment_it',
  'external_cloud_and_ai',
  'purchases_it',
  'research_facilities_it',
] as const;

const categoryColor = computed(() => ({
  equipment_it: colors.value.plum.dark,
  purchases_it: colors.value.lightGreen.dark,
  external_cloud_and_ai:
    CHART_CATEGORY_COLOR_SCHEMES.value.external_cloud_and_ai,
  research_facilities_it:
    CHART_CATEGORY_COLOR_SCHEMES.value.research_facilities,
}));

const WAFFLE_TOTAL_UNITS = 1000;
const WAFFLE_COLS = 50;
const WAFFLE_ROWS = 20;
const WAFFLE_COLS_COMPACT = 100;
const WAFFLE_ROWS_COMPACT = 10;
const NON_IT_COLOR = '#C8C6BE';

const waffleCols = computed(() =>
  props.compact ? WAFFLE_COLS_COMPACT : WAFFLE_COLS,
);
const waffleRows = computed(() =>
  props.compact ? WAFFLE_ROWS_COMPACT : WAFFLE_ROWS,
);

interface WaffleCategory {
  key: string;
  label: string;
  color: string;
  units: number;
  isIT: boolean;
  /** False for IT categories whose source module is not yet validated. */
  validated: boolean;
}

function largestRemainder(values: number[], target: number): number[] {
  if (values.length === 0) return [];
  const floors = values.map((v) => Math.floor(v));
  const remainder = target - floors.reduce((a, b) => a + b, 0);
  const indexed = values.map((v, i) => ({ i, frac: v - Math.floor(v) }));
  indexed.sort((a, b) => b.frac - a.frac);
  for (let k = 0; k < remainder; k++) floors[indexed[k].i]++;
  return floors;
}

function waffleUnitsToPercentLabel(units: number): string {
  if (units % 10 === 0) return `${units / 10}%`;
  return `${(units / 10).toFixed(1)}%`;
}

function isTinyNonZeroPercent(units: number): boolean {
  return units > 0 && units < 10;
}

function waffleUnitsToLegendLabel(units: number): string {
  if (isTinyNonZeroPercent(units)) return '<1%';
  return waffleUnitsToPercentLabel(units);
}

const validatedKeys = computed(
  () => new Set(props.data.validated_sources ?? []),
);

const waffleCategoryData = computed<WaffleCategory[]>(() => {
  const totalItUnits = Math.min(
    WAFFLE_TOTAL_UNITS,
    Math.max(
      0,
      Math.round((props.data.percentage_of_source_modules ?? 0) * 10),
    ),
  );

  const validatedCategoryKeys = IT_FOCUS_CATEGORY_ORDER.filter((key) =>
    validatedKeys.value.has(key),
  );

  const validatedTotalTonnes = validatedCategoryKeys.reduce((sum, key) => {
    const cat = props.data.categories.find((c) => c.category_key === key);
    return sum + (cat?.tonnes_co2eq ?? 0);
  }, 0);

  const rawUnits = validatedCategoryKeys.map((key) => {
    const cat = props.data.categories.find((c) => c.category_key === key);
    if (!cat || validatedTotalTonnes <= 0) return 0;
    return (cat.tonnes_co2eq / validatedTotalTonnes) * totalItUnits;
  });

  const rounded = largestRemainder(rawUnits, totalItUnits);
  const unitsByKey = new Map(
    validatedCategoryKeys.map((key, i) => [key, rounded[i]] as const),
  );

  // Keep all IT categories in display order; unvalidated ones carry 0 units
  // (no waffle cells) and are flagged so the legend can grey them out.
  const cats: WaffleCategory[] = IT_FOCUS_CATEGORY_ORDER.map((key) => ({
    key,
    label: t(CATEGORY_LABEL_MAP[key] ?? key),
    color:
      categoryColor.value[key as keyof typeof categoryColor.value] ?? '#999',
    units: unitsByKey.get(key) ?? 0,
    isIT: true,
    validated: validatedKeys.value.has(key),
  }));

  cats.push({
    key: 'non_it',
    label: t('it-focus-other-emissions'),
    color: NON_IT_COLOR,
    units: WAFFLE_TOTAL_UNITS - totalItUnits,
    isIT: false,
    validated: true,
  });

  return cats;
});

const cellSize = computed(() =>
  Math.max(4, waffleWidth.value / waffleCols.value),
);
const waffleHeight = computed(() => cellSize.value * waffleRows.value);
const hasWaffleSize = computed(() => waffleWidth.value > 0);

const waffleChartOption = computed<EChartsOption>(() => {
  const cats = waffleCategoryData.value;
  if (!cats.length) return { series: [] };

  const cells: WaffleCategory[] = [];
  cats.forEach((cat) => {
    for (let i = 0; i < cat.units; i++) cells.push(cat);
  });

  const size = cellSize.value;

  const decalForIndex = (idx: number) => {
    if (!colorblindStore.enabled) return undefined;
    return {
      symbol: 'rect',
      dashArrayX: [2, 2],
      dashArrayY: [2, 4],
      rotation: (Math.PI / 6) * (idx % 6),
      color: 'rgba(0, 0, 0, 0.55)',
      lineWidth: 1.1,
    } as unknown;
  };

  const series = cats.map((cat, idx) => {
    const decal = cat.isIT ? decalForIndex(idx) : undefined;

    return {
      type: 'scatter' as const,
      name: cat.label,
      symbol: 'rect' as const,
      symbolSize: size,
      data: cells
        .map((c, idx) => ({ c, idx }))
        .filter(({ c }) => c.key === cat.key)
        .map(({ idx }) => [
          idx % waffleCols.value,
          Math.floor(idx / waffleCols.value),
        ]),
      itemStyle: cat.isIT
        ? {
            color: cat.color,
            borderColor: '#ffffff',
            borderWidth: 2,
            opacity: 1,
            decal: decal as never,
          }
        : {
            color: '#ffffff',
            borderColor: NON_IT_COLOR,
            borderWidth: 1.3,
            opacity: 0.6,
          },
      emphasis: {
        scale: false,
        itemStyle: cat.isIT
          ? { opacity: 0.75 }
          : { borderWidth: 2, opacity: 0.9 },
      },
      zlevel: cat.isIT ? 2 : 1,
      decal: decal as never,
    };
  });

  return {
    animation: !props.printMode,
    animationDuration: 600,
    animationEasing: 'cubicOut' as const,
    grid: { left: 0, right: 0, top: 0, bottom: 0, containLabel: false },
    xAxis: {
      type: 'value' as const,
      min: -0.5,
      max: waffleCols.value - 0.5,
      show: false,
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value' as const,
      min: -0.5,
      max: waffleRows.value - 0.5,
      show: false,
      splitLine: { show: false },
      inverse: true,
    },
    tooltip: { show: false },
    aria: {
      enabled: true,
      decal: buildChartDecal(colorblindStore.enabled, {
        color: 'rgba(0, 0, 0, 0.55)',
        lineWidth: 1.1,
      }),
    },
    series,
  };
});

const downloadPNG = () =>
  downloadEchartAsPng(chartRef.value?.chart, 'it-focus');

defineExpose({ downloadPNG });
</script>

<template>
  <div>
    <div class="waffle-header q-mt-lg q-mb-xs">
      <div class="flex items-center no-wrap">
        <span class="text-subtitle1 text-weight-medium">{{
          $t('it-focus-breakdown-bar-title')
        }}</span>
        <q-icon
          name="o_info"
          size="14px"
          color="grey-5"
          class="cursor-pointer q-ml-xs"
          :aria-label="$t('results-charts-it-focus-breakdown-title')"
        >
          <q-tooltip
            anchor="center right"
            self="top right"
            class="u-tooltip text-body2"
            max-width="min(92vw, 48rem)"
            :offset="[8, 8]"
          >
            {{ $t('results-charts-it-focus-breakdown-title') }}
          </q-tooltip>
        </q-icon>
      </div>
      <div class="text-caption waffle-caption q-mt-xs">
        {{ $t('it-focus-waffle-caption') }}
      </div>
    </div>

    <div ref="waffleContainerRef" class="q-mt-sm" style="width: 100%">
      <v-chart
        v-if="hasWaffleSize"
        ref="chartRef"
        :key="colorblindStore.enabled ? 'cb' : 'default'"
        :option="waffleChartOption"
        autoresize
        :style="{ height: `${waffleHeight}px`, width: '100%' }"
        @vue:mounted="onChartReady"
      />
    </div>

    <div class="waffle-legend q-mt-sm q-mb-lg">
      <div class="waffle-legend-row">
        <span
          v-for="cat in waffleCategoryData"
          :key="cat.key"
          class="waffle-legend-item"
          :class="{ 'waffle-legend-item--unvalidated': !cat.validated }"
        >
          <span
            v-if="cat.isIT && cat.validated"
            class="waffle-swatch"
            :style="{ backgroundColor: cat.color }"
          />
          <span
            v-else-if="cat.isIT"
            class="waffle-swatch waffle-swatch--unvalidated"
          />
          <span
            v-else
            class="waffle-swatch waffle-swatch--outlined"
            :style="{ borderColor: cat.color }"
          />
          <span
            class="waffle-legend-label"
            :class="{ 'waffle-legend-label--muted': !cat.isIT }"
            style="
              color: color-mix(
                in srgb,
                var(--semantic-color-text) 78%,
                transparent
              );
            "
          >
            {{ cat.label }}
          </span>
          <span
            class="waffle-legend-pct"
            style="
              color: color-mix(
                in srgb,
                var(--semantic-color-text) 72%,
                transparent
              );
            "
          >
            {{
              cat.validated
                ? waffleUnitsToLegendLabel(cat.units)
                : $t('it-focus-not-validated')
            }}
          </span>
        </span>
      </div>
    </div>

    <Teleport to="body">
      <TooltipEcharts
        v-if="tooltip.visible"
        :tooltip-state="tooltip.data"
        :style="style"
      />
    </Teleport>
  </div>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens/decisions' as dec;

.waffle-caption {
  color: dec.$color-text-muted;
  letter-spacing: 0.02em;
}

.waffle-legend {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.waffle-legend-row {
  display: flex;
  flex-wrap: wrap;
  gap: dec.$spacing-md;
  padding: dec.$spacing-sm 0;
}

.waffle-legend-item {
  display: flex;
  align-items: center;
  gap: dec.$spacing-xs;
}

.waffle-legend-item--unvalidated {
  opacity: 0.45;
}

.waffle-swatch {
  width: dec.$spacing-md;
  height: dec.$spacing-md;
  flex-shrink: 0;
  display: inline-block;
  margin-right: dec.$spacing-xs;
}

.waffle-swatch--outlined {
  border: 1.3px solid;
  opacity: 0.6;
}

.waffle-swatch--unvalidated {
  background: repeating-linear-gradient(
    45deg,
    #c8c6be,
    #c8c6be 2px,
    #e4e2db 2px,
    #e4e2db 4px
  );
}

.waffle-legend-label {
  font-size: dec.$text-size-xs;
  font-weight: dec.$text-weight-medium;
}

.waffle-legend-label--muted {
  font-weight: dec.$text-weight-regular;
  color: dec.$color-text-muted;
}

.waffle-legend-pct {
  font-size: dec.$text-size-xs;
  color: dec.$color-text-muted;
}
</style>
