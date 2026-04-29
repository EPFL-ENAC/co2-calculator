<script setup lang="ts">
import { computed, onMounted, onUpdated, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import { graphic } from 'echarts';
import {
  GraphicComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { useWorkspaceStore } from 'src/stores/workspace';
import {
  CHART_CATEGORY_COLOR_SCHEMES,
  colors,
  getModuleForCategoryKey,
  RESULTS_CATEGORY_LABEL_KEYS,
  RESULTS_CATEGORY_ORDER,
} from 'src/constant/charts';
import { renderTooltipHtml } from 'src/composables/useEchartsTooltip';
import { extractReductionObjectiveEpflTooltipState } from 'src/utils/chart-tooltip-extractors';

interface Props {
  hideResearchFacilities?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  hideResearchFacilities: false,
});

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
  GraphicComponent,
]);

type FootprintRow = { year: number; category: string; co2: number };
type PopulationRow = { year: number; pop: number };

const { t, te } = useI18n();

const INT_FORMATTER = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 0,
});

const yearConfigStore = useYearConfigStore();
const workspaceStore = useWorkspaceStore();

const currentYear = computed(
  () => workspaceStore.selectedYear ?? new Date().getFullYear(),
);

const YEARS_END = 2040;

function buildPiecewiseEasedTotalsByYear(params: {
  years: readonly number[];
  startYear: number;
  startTotal: number;
  anchors: ReadonlyArray<{ year: number; total: number }>;
}): Record<number, number> {
  const { years, startYear, startTotal } = params;

  const anchors = [...params.anchors]
    .filter((a) => a.year >= startYear)
    .sort((a, b) => a.year - b.year);

  const points: Array<{ year: number; total: number }> = [
    { year: startYear, total: startTotal },
    ...anchors,
  ];

  const yearSet = new Set(years);
  const out: Record<number, number> = {};

  for (let i = 0; i < points.length; i += 1) {
    const p0 = points[i];
    const p1 = points[i + 1];

    if (!p1) {
      for (const y of years) {
        if (y < p0.year) continue;
        out[y] = p0.total;
      }
      break;
    }

    const span = p1.year - p0.year;
    for (let y = p0.year; y <= p1.year; y += 1) {
      if (!yearSet.has(y)) continue;
      const tt = span === 0 ? 1 : (y - p0.year) / span;
      const eased = 1 - Math.pow(1 - tt, 2);
      out[y] = p0.total + (p1.total - p0.total) * eased;
    }
  }

  return out;
}

const reductionObjectives = computed(() => {
  const ro = yearConfigStore.config?.config?.reduction_objectives;
  return ro ?? null;
});

const epflFootprintRows = computed<FootprintRow[]>(() => {
  const raw = reductionObjectives.value?.institutional_footprint ?? [];
  return (raw as unknown[]).filter(Boolean).map((r) => {
    const row = r as FootprintRow;
    return {
      ...row,
      co2: typeof row.co2 === 'number' ? row.co2 / 1000 : row.co2,
    };
  }) as FootprintRow[];
});

const epflPopulationRows = computed<PopulationRow[]>(() => {
  const raw = reductionObjectives.value?.population_projections ?? [];
  return (raw as unknown[]).filter(Boolean) as PopulationRow[];
});

const epflGoals = computed(
  () => reductionObjectives.value?.goals?.slice() ?? [],
);

const yearsStart = computed(() => {
  const candidates: number[] = [];

  for (const r of epflFootprintRows.value) {
    if (typeof r.year === 'number') candidates.push(r.year);
  }
  for (const r of epflPopulationRows.value) {
    if (typeof r.year === 'number') candidates.push(r.year);
  }
  for (const g of epflGoals.value) {
    if (typeof g?.reference_year === 'number')
      candidates.push(g.reference_year);
  }

  const rawMin = candidates.length
    ? Math.min(...candidates)
    : currentYear.value;
  return Math.min(Math.max(rawMin, 0), YEARS_END);
});

const years = computed(() => {
  const start = yearsStart.value;
  return Array.from({ length: YEARS_END - start + 1 }, (_, i) => start + i);
});

const epflFootprintRowsForChart = computed(() => {
  const rows = epflFootprintRows.value;
  if (!props.hideResearchFacilities) return rows;
  return rows.filter((r) => r.category !== 'research_facilities');
});

const epflFootprintByYearCategory = computed(() => {
  const out = new Map<number, Map<string, number>>();
  for (const r of epflFootprintRowsForChart.value) {
    if (typeof r.year !== 'number') continue;
    const key = r.category;
    const bucket = out.get(r.year) ?? new Map<string, number>();
    bucket.set(
      key,
      (bucket.get(key) ?? 0) + (typeof r.co2 === 'number' ? r.co2 : 0),
    );
    out.set(r.year, bucket);
  }
  return out;
});

const epflFootprintTotalsByYear = computed(() => {
  const out = new Map<number, number>();
  for (const [year, byCat] of epflFootprintByYearCategory.value.entries()) {
    let sum = 0;
    for (const v of byCat.values()) sum += v;
    out.set(year, sum);
  }
  return out;
});

function getEpflYearCategorySums(year: number): Record<string, number> {
  const byCat = epflFootprintByYearCategory.value.get(year);
  if (!byCat) return {};
  return Object.fromEntries(byCat.entries());
}

function getEpflYearTotal(year: number): number {
  return epflFootprintTotalsByYear.value.get(year) ?? 0;
}

const epflBaselineYear = computed(() => {
  return years.value.find((y) => getEpflYearTotal(y) > 0) ?? yearsStart.value;
});

function categoryColor(categoryKey: string): string {
  return CHART_CATEGORY_COLOR_SCHEMES.value[categoryKey] ?? '#CFD4EE';
}

function categoryLabel(categoryKey: string): string {
  const labelKey =
    RESULTS_CATEGORY_LABEL_KEYS[
      categoryKey as keyof typeof RESULTS_CATEGORY_LABEL_KEYS
    ];
  if (labelKey && te(labelKey)) return t(labelKey);

  const mod = getModuleForCategoryKey(categoryKey);
  if (mod && te(mod)) return t(mod);
  return categoryKey;
}

const TOOLTIP_CATEGORY_ORDER = RESULTS_CATEGORY_ORDER;

function tooltipSortIndex(seriesName: string): number {
  const idx = TOOLTIP_CATEGORY_ORDER.indexOf(
    seriesName as (typeof TOOLTIP_CATEGORY_ORDER)[number],
  );
  return idx === -1 ? 999 : idx;
}

// ── Data fetch ───────────────────────────────────────────────────────────────
const lastFetchedYear = ref<number | null>(null);

function readCssVarHex(name: string): string | null {
  try {
    if (typeof window === 'undefined') return null;
    const v = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    return v || null;
  } catch {
    return null;
  }
}

const accentColorHex = ref<string | null>(null);

const tooltipFormatter = (params: unknown) =>
  renderTooltipHtml(
    extractReductionObjectiveEpflTooltipState(params, {
      years: years.value,
      accentColor: accentColorHex.value ?? colors.value.cobalt.darker,
      totalLabel: t('results_objectives_total'),
      categoryColor,
      categoryLabel,
      tooltipSortIndex,
      populationLabel: t('results_objectives_population_forecast'),
      formatPopulation: (v) =>
        v == null ? '-' : INT_FORMATTER.format(Math.round(v)),
    }),
  );

async function ensureYearConfigFetched(): Promise<void> {
  const y = currentYear.value;
  if (lastFetchedYear.value === y) return;
  lastFetchedYear.value = y;
  await yearConfigStore.fetchConfig(y);
}

onMounted(async () => {
  accentColorHex.value = readCssVarHex('--q-accent');
  await ensureYearConfigFetched();
});

onUpdated(async () => {
  await ensureYearConfigFetched();
});

const populationSeries = computed(() => {
  const pop = epflPopulationRows.value;
  if (!pop.length) return null;
  const popByYear = Object.fromEntries(pop.map((r) => [r.year, r.pop]));
  const firstPopYear = pop.reduce<number | null>((min, r) => {
    if (typeof r.year !== 'number') return min;
    if (typeof r.pop !== 'number') return min;
    return min == null ? r.year : Math.min(min, r.year);
  }, null);
  const firstPopValue =
    firstPopYear == null ? null : (popByYear[firstPopYear] ?? null);

  const baselineYear = epflBaselineYear.value;
  const baselineIdx = Math.max(0, years.value.indexOf(baselineYear));
  const lastIdx = years.value.length - 1;

  const popAtBaseline = (() => {
    const v = popByYear[baselineYear];
    if (typeof v === 'number') return v;
    if (firstPopYear != null && baselineYear < firstPopYear) {
      return typeof firstPopValue === 'number' ? firstPopValue : null;
    }
    return null;
  })();

  const popForYear = (y: number): number | null => {
    const v = popByYear[y];
    if (typeof v === 'number') return v;
    if (firstPopYear != null && y < firstPopYear) {
      return typeof firstPopValue === 'number' ? firstPopValue : null;
    }
    return null;
  };

  return {
    name: 'population',
    type: 'line',
    xAxisIndex: 1,
    yAxisIndex: 1,
    showSymbol: false,
    symbol: 'circle',
    symbolSize: 7,
    zlevel: 6,
    z: 60,
    lineStyle: { type: 'dotted', width: 2, color: '#ff0000' },
    itemStyle: {
      color: '#ff0000',
      borderColor: '#ffffff',
      borderWidth: 2,
    },
    tooltip: { show: false },
    data:
      popAtBaseline == null
        ? years.value.map((y) => popForYear(y))
        : [
            { value: [baselineIdx - 0.5, popAtBaseline] },
            { value: [baselineIdx + 0.5, popAtBaseline] },
            ...years.value
              .filter((y) => y >= baselineYear + 1)
              .map((y) => ({
                value: [years.value.indexOf(y), popForYear(y)],
              })),
            { value: [lastIdx + 0.5, popForYear(years.value[lastIdx])] },
          ],
  };
});

type EpflSeriesPayload = {
  stackedSeries: unknown[];
  totalsByYear: Record<number, number>;
  baselineYear: number;
};

const epflSeriesData = computed<EpflSeriesPayload | null>(() => {
  const footprint = epflFootprintRowsForChart.value;
  const goals = epflGoals.value;
  if (footprint.length === 0) return null;

  const baselineYear = epflBaselineYear.value;
  const baselineByCat = getEpflYearCategorySums(baselineYear);
  const baselineTotal = Object.values(baselineByCat).reduce((a, b) => a + b, 0);
  if (baselineTotal <= 0) return null;

  const anchors: Array<{ year: number; total: number }> = [];
  for (const g of goals) {
    const refTotal = getEpflYearTotal(g.reference_year);
    if (refTotal <= 0) continue;
    anchors.push({
      year: g.target_year,
      total: refTotal * (1 - g.reduction_percentage),
    });
  }

  const totalsByYear = buildPiecewiseEasedTotalsByYear({
    years: years.value,
    startYear: baselineYear,
    startTotal: baselineTotal,
    anchors,
  });

  const baselineIdx = Math.max(0, years.value.indexOf(baselineYear));
  const lastIdx = years.value.length - 1;

  const categoryKeys = [
    ...TOOLTIP_CATEGORY_ORDER.filter((k) => baselineByCat[k] != null),
    ...Object.keys(baselineByCat).filter(
      (k) => !TOOLTIP_CATEGORY_ORDER.includes(k as never),
    ),
  ];

  const totalColor = accentColorHex.value ?? colors.value.cobalt.darker;
  const totalLineData = [
    { value: [baselineIdx - 0.5, baselineTotal] },
    { value: [baselineIdx + 0.5, baselineTotal] },
    ...years.value
      .filter((y) => y >= baselineYear + 1)
      .map((y) => ({ value: [years.value.indexOf(y), totalsByYear[y] ?? 0] })),
    { value: [lastIdx + 0.5, totalsByYear[years.value[lastIdx]] ?? 0] },
  ];

  const totalAreaSeries = {
    name: 'total',
    type: 'line',
    xAxisIndex: 1,
    showSymbol: false,
    symbol: 'none',
    lineStyle: { width: 0 },
    itemStyle: { opacity: 0 },
    areaStyle: {
      color: new graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: totalColor },
        { offset: 1, color: 'rgba(255,255,255,0)' },
      ]),
      opacity: 0.18,
    },
    emphasis: { disabled: true },
    zlevel: 1,
    z: 1,
    data: totalLineData,
    tooltip: { show: false },
  };

  const totalLineSeries = {
    name: 'total',
    type: 'line',
    xAxisIndex: 1,
    showSymbol: false,
    symbol: 'circle',
    symbolSize: 8,
    lineStyle: { width: 2.5, color: totalColor },
    itemStyle: {
      color: totalColor,
      borderColor: '#ffffff',
      borderWidth: 2,
    },
    areaStyle: { opacity: 0 },
    emphasis: { focus: 'series' },
    zlevel: 5,
    z: 50,
    data: totalLineData,
    tooltip: { show: false },
  };

  const baselineStackedBars = categoryKeys
    .map((cat) => {
      const color = categoryColor(cat);
      return {
        name: cat,
        type: 'bar',
        stack: 'baseline',
        barWidth: '100%',
        itemStyle: { color },
        emphasis: { focus: 'series' },
        zlevel: 2,
        z: 2,
        data: years.value.map((y) => {
          if (y !== baselineYear) return null;
          return baselineByCat[cat] ?? 0;
        }),
      };
    })
    .reverse();

  return {
    stackedSeries: [...baselineStackedBars, totalAreaSeries, totalLineSeries],
    totalsByYear,
    baselineYear,
  };
});

const showEpflEmptyState = computed(() => !epflSeriesData.value);

const chartOption = computed<EChartsOption | null>(() => {
  const payload = epflSeriesData.value;
  if (!payload) return null;
  const popSeries = populationSeries.value;
  const popRows = epflPopulationRows.value;
  const popByYear = Object.fromEntries(popRows.map((r) => [r.year, r.pop]));
  const firstPopYear = popRows.reduce<number | null>((min, r) => {
    if (typeof r.year !== 'number') return min;
    if (typeof r.pop !== 'number') return min;
    return min == null ? r.year : Math.min(min, r.year);
  }, null);
  const firstPopValue =
    firstPopYear == null ? null : (popByYear[firstPopYear] ?? null);
  const popForYear = (y: number): number | null => {
    const v = popByYear[y];
    if (typeof v === 'number') return v;
    if (firstPopYear != null && y < firstPopYear) {
      return typeof firstPopValue === 'number' ? firstPopValue : null;
    }
    return null;
  };

  const totalTooltipSeries = {
    name: 'total',
    type: 'line',
    xAxisIndex: 0,
    yAxisIndex: 0,
    showSymbol: false,
    symbol: 'none',
    lineStyle: { width: 0 },
    itemStyle: { opacity: 0 },
    silent: true,
    data: years.value.map((y) =>
      y < payload.baselineYear ? null : (payload.totalsByYear[y] ?? 0),
    ),
  };

  const populationTooltipSeries = {
    name: 'population',
    type: 'line',
    xAxisIndex: 0,
    yAxisIndex: 1,
    showSymbol: false,
    symbol: 'none',
    lineStyle: { width: 0 },
    itemStyle: { opacity: 0 },
    silent: true,
    data: years.value.map((y) => popForYear(y)),
  };

  return {
    axisPointer: {
      // Link category (year labels) and hidden numeric x-axis (index-based)
      // so "axis" tooltips include series rendered on xAxisIndex: 1.
      link: [{ xAxisIndex: [0, 1] }],
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
      },
      formatter: tooltipFormatter,
    },
    legend: { show: false },
    grid: {
      left: 48,
      right: 64,
      top: 24,
      bottom: 24,
      containLabel: true,
    },
    xAxis: [
      {
        type: 'category',
        boundaryGap: true,
        axisLabel: { interval: 0 },
        axisTick: { interval: 0, alignWithLabel: true },
        data: years.value.map(String),
      },
      {
        type: 'value',
        min: -0.5,
        max: years.value.length - 1 + 0.5,
        axisPointer: { show: false },
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { show: false },
        splitLine: { show: false },
      },
    ],
    yAxis: [
      {
        type: 'value',
        name: t('results_units_tonnes'),
        min: 0,
        nameGap: 36,
        nameLocation: 'middle',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { formatter: (v: number) => `${v.toFixed(1)}` },
        splitLine: { show: false },
      },
      {
        type: 'value',
        name: t('results_objectives_population_axis'),
        min: 0,
        position: 'right',
        nameGap: 56,
        nameLocation: 'middle',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { formatter: (v: number) => INT_FORMATTER.format(v) },
        splitLine: { show: false },
      },
    ],
    series: popSeries
      ? [
          ...payload.stackedSeries,
          popSeries,
          totalTooltipSeries,
          populationTooltipSeries,
        ]
      : [...payload.stackedSeries, totalTooltipSeries, populationTooltipSeries],
  } as EChartsOption;
});
</script>

<template>
  <div class="objective-chart">
    <VChart
      v-if="chartOption && !showEpflEmptyState"
      :option="chartOption"
      autoresize
      class="objective-chart__canvas"
    />
    <q-card v-else flat class="objective-empty-card">
      <q-card-section class="objective-empty-card__content">
        <q-icon name="o_info" size="md" color="accent" class="q-mb-md" />
        <div class="text-h6 text-weight-medium text-center q-mb-sm">
          {{ $t('results_objectives_epfl_no_data_title') }}
        </div>
        <div class="text-body2 text-secondary text-center">
          {{ $t('results_objectives_epfl_no_data_message') }}
        </div>
      </q-card-section>
    </q-card>
  </div>
</template>

<style scoped lang="scss">
.objective-chart {
  height: 100%;
  min-height: 620px;
}

.objective-chart__canvas {
  width: 100%;
  height: 100%;
  min-height: 620px;
}

.objective-chart__empty {
  height: 100%;
  width: 100%;
  background: rgba(0, 0, 0, 0.01);
  border: 1px dashed rgba(0, 0, 0, 0.01);
  border-radius: 8px;
}

.objective-empty-card {
  min-height: 620px;
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  background-color: rgba(0, 0, 0, 0.02);
}

.objective-empty-card__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
}

.objective-subtitle__link {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
}
</style>

<style lang="scss">
/* ECharts tooltip is rendered outside component root; keep these global. */
.objective-tooltip {
  min-width: 220px;
}

.objective-tooltip__title {
  font-weight: 600;
  margin-bottom: 6px;
}

.objective-tooltip__line {
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 1.35;
}

.objective-tooltip__line--total {
  margin-bottom: 4px;
}

.objective-tooltip__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  display: inline-block;
  flex: 0 0 auto;
  background: var(--dot-color);
}

.objective-tooltip__dot--population {
  background: #ff0000;
}

.objective-tooltip__label {
  flex: 1;
  opacity: 0.9;
}

.objective-tooltip__label--strong {
  opacity: 0.95;
  font-weight: 600;
}

.objective-tooltip__value {
  font-variant-numeric: tabular-nums;
}

.objective-tooltip__value--strong {
  font-weight: 600;
}

.objective-tooltip__section {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
}
</style>
