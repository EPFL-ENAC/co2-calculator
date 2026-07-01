<script setup lang="ts">
import { computed, nextTick, ref, type PropType } from 'vue';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import { TooltipComponent, GridComponent } from 'echarts/components';
import VChart from 'vue-echarts';
import TooltipEcharts from './TooltipEcharts.vue';
import { useEchartsTooltip } from './useEchartsTooltip';
import type { TooltipRow, TooltipState } from 'src/types/chartTooltip';
import {
  normalizeAxisParams,
  extractSeriesValue,
  formatTooltipTonnes,
} from 'src/utils/chart-tooltip-extractors';

use([CanvasRenderer, BarChart, TooltipComponent, GridComponent]);

// Keep the bars readable when only a couple of years are shown.
const MAX_BAR_WIDTH = 96;

export interface CompareYearsSeries {
  key: string;
  label: string;
  color: string;
}

/** A single solid bar appended after the year bars (e.g. reduction objective). */
export interface CompareYearsObjectiveBar {
  label: string;
  value: number;
  color: string;
}

const props = defineProps({
  years: {
    type: Array as PropType<number[]>,
    required: true,
  },
  series: {
    type: Array as PropType<CompareYearsSeries[]>,
    required: true,
  },
  /** year → (series key → tonnes CO2eq). */
  dataByYear: {
    type: Object as PropType<Record<number, Record<string, number>>>,
    required: true,
  },
  /** Optional trailing single-value bars, each with its own category tick. */
  objectives: {
    type: Array as PropType<CompareYearsObjectiveBar[]>,
    default: () => [],
  },
});

// ── Teleport tooltip composable (shared look & feel with the result charts) ──
const { tooltip, style, attach, emitTooltip } = useEchartsTooltip();

const chartRef = ref<InstanceType<typeof VChart>>();

const onChartReady = async () => {
  await nextTick();
  const chart = chartRef.value?.chart;
  if (!chart) return;
  attach(chart);
};

// series label → swatch colour, for the teleport tooltip dots.
const colorByName = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {};
  for (const s of props.series) map[s.label] = s.color;
  for (const o of props.objectives) map[o.label] = o.color;
  return map;
});

function buildTooltipState(rawParams: unknown): TooltipState {
  const params = normalizeAxisParams(rawParams);
  if (!params.length) return null;

  const title = String(params[0]?.axisValue ?? '');

  // Only the categories that actually contribute at the hovered bar.
  const rows: TooltipRow[] = params
    .map((p) => ({ p, value: extractSeriesValue(p.value) }))
    .filter(({ value }) => typeof value === 'number' && value > 0)
    .map(
      ({ p, value }): TooltipRow => ({
        label: String(p.seriesName ?? ''),
        value: formatTooltipTonnes(value),
        color: colorByName.value[String(p.seriesName ?? '')],
      }),
    );

  if (!rows.length) return null;
  return { title, rows };
}

const chartOption = computed<EChartsOption>(() => {
  // Only keep series that contribute a non-zero value across the shown years.
  const visibleSeries = props.series.filter((s) =>
    props.years.some((y) => (props.dataByYear[y]?.[s.key] ?? 0) > 0),
  );

  const objectives = props.objectives;

  const categories = [
    ...props.years.map((y) => String(y)),
    ...objectives.map((o) => o.label),
  ];

  const stackedSeries = visibleSeries.map((s) => ({
    name: s.label,
    type: 'bar' as const,
    stack: 'total',
    barMaxWidth: MAX_BAR_WIDTH,
    itemStyle: { color: s.color },
    emphasis: { focus: 'series' as const },
    // Trailing `null`s leave the objective slots empty for stacked categories.
    data: [
      ...props.years.map((y) => props.dataByYear[y]?.[s.key] ?? 0),
      ...objectives.map(() => null),
    ],
  }));

  // One series per objective, sharing the year bars' stack name so each slot
  // holds a single, centered bar (a distinct stack would render them
  // side-by-side). Each series is null everywhere except its own trailing slot.
  const objectiveSeries = objectives.map((o, i) => ({
    name: o.label,
    type: 'bar' as const,
    stack: 'total',
    barMaxWidth: MAX_BAR_WIDTH,
    itemStyle: { color: o.color },
    data: [
      ...props.years.map(() => null),
      ...objectives.map((_, j) => (j === i ? o.value : null)),
    ],
  }));

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (rawParams: unknown) => {
        emitTooltip(buildTooltipState(rawParams));
        return '';
      },
    },
    grid: { left: 8, right: 16, top: 12, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: categories,
    },
    yAxis: {
      type: 'value',
    },
    series: [...stackedSeries, ...objectiveSeries],
  };
});
</script>

<template>
  <v-chart
    ref="chartRef"
    class="compare-years-chart"
    autoresize
    :option="chartOption"
    :update-options="{ replaceMerge: ['series'] }"
    @vue:mounted="onChartReady"
  />
  <Teleport to="body">
    <tooltip-echarts
      v-if="tooltip.visible"
      :tooltip-state="tooltip.data"
      :style="style"
    />
  </Teleport>
</template>

<style scoped>
.compare-years-chart {
  width: 100%;
  height: 240px;
}
</style>
