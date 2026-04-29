<script setup lang="ts">
import { computed, onMounted, onUpdated, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
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
import { useModuleStore, useTimelineStore } from 'src/stores/modules';
import {
  CHART_CATEGORY_COLOR_SCHEMES,
  getModuleForCategoryKey,
  RESULTS_CATEGORY_LABEL_KEYS,
  RESULTS_CATEGORY_ORDER,
} from 'src/constant/charts';
import { MODULE_STATES } from 'src/constant/moduleStates';
import { formatTonnesForChart } from 'src/utils/number';

interface Props {
  hideResearchFacilities?: boolean;
  hideAdditionalData?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  hideResearchFacilities: false,
  hideAdditionalData: false,
});

use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
  GraphicComponent,
]);

type PopulationRow = { year: number; pop: number };

const { t, te } = useI18n();

const INT_FORMATTER = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 0,
});

const yearConfigStore = useYearConfigStore();
const workspaceStore = useWorkspaceStore();
const moduleStore = useModuleStore();
const timelineStore = useTimelineStore();

const currentYear = computed(
  () => workspaceStore.selectedYear ?? new Date().getFullYear(),
);

const YEARS_END = 2040;

const reductionObjectives = computed(() => {
  const ro = yearConfigStore.config?.config?.reduction_objectives;
  return ro ?? null;
});

const epflPopulationRows = computed<PopulationRow[]>(() => {
  const raw = reductionObjectives.value?.population_projections ?? [];
  return (raw as unknown[]).filter(Boolean) as PopulationRow[];
});

const yearsStart = computed(() => {
  const candidates: number[] = [];
  for (const r of epflPopulationRows.value) {
    if (typeof r.year === 'number') candidates.push(r.year);
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

function categoryTooltipKey(categoryKey: string): string {
  return `results_objectives_unit_category_tooltip_${categoryKey}`;
}

// ── Unit-mode sliders (right panel) ─────────────────────────────────────────
const unitScenarioPreset = ref<'bau' | 'middle' | 'ambitious'>('bau');
const UNIT_CATEGORY_KEYS = RESULTS_CATEGORY_ORDER;
const ADDITIONAL_UNIT_CATEGORY_KEYS = new Set([
  'commuting',
  'food',
  'waste',
  'embodied_energy',
]);
const TOOLTIP_CATEGORY_ORDER = RESULTS_CATEGORY_ORDER;

type TooltipAxisParam = {
  axisValue?: string;
  seriesName?: string;
  value?: number | (number | null)[] | null;
};

function normalizeTooltipParams(rawParams: unknown): TooltipAxisParam[] {
  if (!Array.isArray(rawParams)) return [];
  return rawParams as TooltipAxisParam[];
}

function extractTooltipSeriesValue(
  raw: TooltipAxisParam['value'],
): number | null {
  if (typeof raw === 'number') return raw;
  if (!Array.isArray(raw)) return null;
  return (raw.length >= 2 ? raw[1] : raw[0]) as number | null;
}

function formatTooltipTonnes(value: number | null): string {
  if (value == null) return '-';
  if (value < 0) return value.toFixed(1);
  return formatTonnesForChart(value);
}

function formatTooltipPopulation(value: number | null): string {
  if (value == null) return '-';
  return INT_FORMATTER.format(Math.round(value));
}

function tooltipSortIndex(seriesName: string): number {
  const idx = TOOLTIP_CATEGORY_ORDER.indexOf(
    seriesName as (typeof TOOLTIP_CATEGORY_ORDER)[number],
  );
  return idx === -1 ? 999 : idx;
}

function renderTooltipCategoryLines(params: TooltipAxisParam[]): string {
  return params
    .filter((p) => p.seriesName && p.value != null)
    .filter((p) => String(p.seriesName) !== 'population')
    .sort((a, b) => {
      const ak = String(a.seriesName ?? '');
      const bk = String(b.seriesName ?? '');
      return tooltipSortIndex(ak) - tooltipSortIndex(bk);
    })
    .map((p) => {
      const key = String(p.seriesName);
      const color = categoryColor(key);
      const value = extractTooltipSeriesValue(p.value);
      const formatted = formatTooltipTonnes(value);
      const label = categoryLabel(key);
      return `
        <div style="display:flex;align-items:center;gap:8px;line-height:1.35;">
          <span style="width:8px;height:8px;border-radius:999px;background:${color};display:inline-block;"></span>
          <span style="flex:1;opacity:0.9;">${label}</span>
          <span style="font-variant-numeric:tabular-nums;">${formatted}</span>
        </div>
      `;
    })
    .join('');
}

function renderTooltipPopulationLine(params: TooltipAxisParam[]): string {
  const p = params.find(
    (x) => String(x.seriesName) === 'population' && x.value != null,
  );
  if (!p) return '';

  const v = extractTooltipSeriesValue(p.value);
  const formatted = formatTooltipPopulation(v);
  const label = t('results_objectives_population_forecast');

  return `
    <div style="margin-top:6px;padding-top:6px;border-top:1px solid rgba(0,0,0,0.12);">
      <div style="display:flex;align-items:center;gap:8px;line-height:1.35;">
        <span style="width:8px;height:8px;border-radius:999px;background:#ff0000;display:inline-block;"></span>
        <span style="flex:1;opacity:1;">${label}</span>
        <span style="font-variant-numeric:tabular-nums;">${formatted}</span>
      </div>
    </div>
  `;
}

function renderTooltipContainer(args: {
  yearLabel: string;
  categoryLines: string;
  populationLine: string;
}): string {
  return `<div style="min-width:220px;">
    <div style="font-weight:600;margin-bottom:6px;">${args.yearLabel}</div>
    ${args.categoryLines}${args.populationLine}
  </div>`;
}

const validatedEmissionCategoryKeys = computed(() => {
  const list = moduleStore.state.emissionBreakdown?.validated_categories ?? [];
  return new Set(list);
});

function isOwningModuleValidated(categoryKey: string): boolean {
  const mod = getModuleForCategoryKey(categoryKey);
  if (!mod) return true;
  return timelineStore.itemStates[mod] === MODULE_STATES.Validated;
}

function isEmissionCategoryValidated(categoryKey: string): boolean {
  return validatedEmissionCategoryKeys.value.has(categoryKey);
}

function isUnitCategoryInteractive(categoryKey: string): boolean {
  if (categoryKey === 'research_facilities' && props.hideResearchFacilities) {
    return false;
  }
  return (
    isEmissionCategoryValidated(categoryKey) &&
    isOwningModuleValidated(categoryKey)
  );
}

const visibleUnitCategoryKeys = computed(() =>
  UNIT_CATEGORY_KEYS.filter((c) => {
    if (props.hideAdditionalData && ADDITIONAL_UNIT_CATEGORY_KEYS.has(c)) {
      return false;
    }
    return isUnitCategoryInteractive(c);
  }),
);

const hasAnyInteractiveUnitCategory = computed(
  () => visibleUnitCategoryKeys.value.length > 0,
);

const unitSliderLevels = ref<Record<string, number>>(
  Object.fromEntries(UNIT_CATEGORY_KEYS.map((c) => [c, 1])),
);

function annualReductionForLevel(level: number): number {
  const clamped = Math.max(1, Math.min(5, level));
  return (clamped - 1) * 0.02;
}

function applyScenarioPreset(preset: typeof unitScenarioPreset.value) {
  const level = preset === 'bau' ? 1 : preset === 'middle' ? 3 : 5;
  if (!hasAnyInteractiveUnitCategory.value) return;

  const next = { ...unitSliderLevels.value };
  for (const c of visibleUnitCategoryKeys.value) {
    next[c] = level;
  }
  unitSliderLevels.value = next;
}

const unitScenarioPresetModel = computed({
  get: () => unitScenarioPreset.value,
  set: (v: typeof unitScenarioPreset.value) => {
    unitScenarioPreset.value = v;
    applyScenarioPreset(v);
  },
});

function resetUnitSliders(): void {
  unitScenarioPreset.value = 'bau';
  unitSliderLevels.value = Object.fromEntries(
    UNIT_CATEGORY_KEYS.map((c) => [c, 1]),
  );
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

async function ensureYearConfigFetched(): Promise<void> {
  const y = currentYear.value;
  if (lastFetchedYear.value === y) return;
  lastFetchedYear.value = y;
  await yearConfigStore.fetchConfig(y);
}

function ensureSlidersResetIfLocked(): void {
  if (hasAnyInteractiveUnitCategory.value) return;
  unitSliderLevels.value = Object.fromEntries(
    UNIT_CATEGORY_KEYS.map((c) => [c, 1]),
  );
}

onMounted(async () => {
  accentColorHex.value = readCssVarHex('--q-accent');
  await ensureYearConfigFetched();
  ensureSlidersResetIfLocked();
});

onUpdated(async () => {
  await ensureYearConfigFetched();
  ensureSlidersResetIfLocked();
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

  return {
    name: 'population',
    type: 'line',
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
    data: years.value.map((y) => {
      const v = popByYear[y];
      if (typeof v === 'number') return v;
      if (firstPopYear != null && y < firstPopYear) return firstPopValue;
      return null;
    }),
  };
});

const unitSeriesData = computed(() => {
  const payload = moduleStore.state.emissionBreakdown;
  if (!payload) return null;
  const breakdown = payload.module_breakdown ?? [];
  const additionalBreakdown = payload.additional_breakdown ?? [];
  const baselineYear = Math.min(
    Math.max(currentYear.value, yearsStart.value),
    YEARS_END,
  );

  const baselineByCat: Record<string, number> = {};

  const sumRowTonnes = (row: {
    emissions?: Array<{ value?: unknown }>;
  }): number => {
    const emissions = row.emissions ?? [];
    return emissions.reduce((s, e) => {
      const v = typeof e.value === 'number' ? e.value : 0;
      return s + v;
    }, 0);
  };

  for (const row of breakdown) {
    const key = row.category_key;
    if (props.hideAdditionalData && ADDITIONAL_UNIT_CATEGORY_KEYS.has(key)) {
      continue;
    }
    if (!isUnitCategoryInteractive(key)) continue;
    baselineByCat[key] = (baselineByCat[key] ?? 0) + sumRowTonnes(row);
  }

  for (const row of additionalBreakdown) {
    const key = row.category_key;
    if (props.hideAdditionalData && ADDITIONAL_UNIT_CATEGORY_KEYS.has(key)) {
      continue;
    }
    if (
      !UNIT_CATEGORY_KEYS.includes(key as (typeof UNIT_CATEGORY_KEYS)[number])
    ) {
      continue;
    }
    if (!isUnitCategoryInteractive(key)) continue;
    baselineByCat[key] = (baselineByCat[key] ?? 0) + sumRowTonnes(row);
  }

  const pop = epflPopulationRows.value;
  const popByYear = Object.fromEntries(pop.map((r) => [r.year, r.pop]));
  const popBase = popByYear[baselineYear] ?? null;

  const series = visibleUnitCategoryKeys.value
    .filter((c) => isUnitCategoryInteractive(c) && (baselineByCat[c] ?? 0) > 0)
    .map((c) => {
      const color = CHART_CATEGORY_COLOR_SCHEMES.value[c] ?? '#CFD4EE';
      const level = unitSliderLevels.value[c] ?? 1;
      const annualReduction = annualReductionForLevel(level);

      const data = years.value.map((y) => {
        if (y < baselineYear) return null;
        if (y === baselineYear) return baselineByCat[c] ?? 0;

        const yearsAhead = y - baselineYear;
        const popFactor = popBase && popByYear[y] ? popByYear[y] / popBase : 1;
        const reducedFactor = Math.pow(1 - annualReduction, yearsAhead);
        return (baselineByCat[c] ?? 0) * popFactor * reducedFactor;
      });

      return {
        name: c,
        type: 'line',
        stack: 'Total',
        showSymbol: false,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 1, color },
        itemStyle: {
          color,
          borderColor: '#ffffff',
          borderWidth: 2,
        },
        areaStyle: { color },
        emphasis: { focus: 'series' },
        data,
      };
    })
    .reverse();

  return { stackedSeries: series };
});

const showUnitEmptyState = computed(() => !hasAnyInteractiveUnitCategory.value);

const chartOption = computed<EChartsOption | null>(() => {
  const payload = unitSeriesData.value;
  if (!payload) return null;
  const popSeries = populationSeries.value;

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: { backgroundColor: '#6a7985' },
      },
      formatter: (rawParams: unknown) => {
        const params = normalizeTooltipParams(rawParams);
        const yearLabel = String(params[0]?.axisValue ?? '');

        return renderTooltipContainer({
          yearLabel,
          categoryLines: renderTooltipCategoryLines(params),
          populationLine: renderTooltipPopulationLine(params),
        });
      },
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
        boundaryGap: false,
        axisLabel: { interval: 0 },
        axisTick: { interval: 0, alignWithLabel: true },
        data: years.value.map(String),
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
      ? [...payload.stackedSeries, popSeries]
      : [...payload.stackedSeries],
  } as EChartsOption;
});
</script>

<template>
  <div class="row items-stretch q-col-gutter-md">
    <div v-if="showUnitEmptyState" class="col-12">
      <q-card flat class="objective-empty-card">
        <q-card-section class="objective-empty-card__content">
          <q-icon name="o_info" size="md" color="accent" class="q-mb-md" />
          <div class="text-h6 text-weight-medium text-center q-mb-sm">
            {{ $t('results_objectives_unit_no_validated_title') }}
          </div>
          <div class="text-body2 text-secondary text-center">
            {{ $t('results_objectives_unit_no_validated_message') }}
          </div>
        </q-card-section>
      </q-card>
    </div>

    <div v-else class="col-12 col-lg">
      <div class="objective-chart">
        <VChart
          v-if="chartOption"
          :option="chartOption"
          autoresize
          class="objective-chart__canvas"
        />
        <div v-else class="objective-chart__empty" />
      </div>
    </div>

    <div v-if="!showUnitEmptyState" class="col-12 col-lg-3">
      <section class="unit-controls">
        <div class="q-pt-xl q-px-lg">
          <div class="row items-center justify-between q-mb-xs">
            <div class="text-caption text-secondary">Scenario</div>
            <q-btn
              no-caps
              unelevated
              outline
              color="accent"
              label="Reset"
              size="sm"
              class="text-weight-medium"
              :disable="!hasAnyInteractiveUnitCategory"
              @click="resetUnitSliders"
            />
          </div>
          <q-select
            v-model="unitScenarioPresetModel"
            dense
            outlined
            emit-value
            map-options
            hide-bottom-space
            :disable="!hasAnyInteractiveUnitCategory"
            :options="[
              { label: 'BAU', value: 'bau' },
              { label: 'Middle of the road', value: 'middle' },
              { label: 'Ambitious', value: 'ambitious' },
            ]"
          />
        </div>

        <q-separator class="q-my-lg" />

        <div class="unit-controls__sliders">
          <div class="unit-controls__scroll column">
            <div
              v-for="cat in visibleUnitCategoryKeys"
              :key="cat"
              class="objective-slider q-px-xl"
              :style="{ '--cat-color': categoryColor(cat) }"
            >
              <div class="objective-slider__header">
                <div class="objective-slider__label text-caption text-primary">
                  <span class="objective-slider__label-text">
                    {{ categoryLabel(cat) }}
                  </span>
                  <q-icon
                    name="o_info"
                    size="14px"
                    class="objective-slider__label-info text-secondary"
                  >
                    <q-tooltip class="text-body2 text-black" max-width="260px">
                      {{
                        $t(categoryTooltipKey(cat), {
                          category: categoryLabel(cat),
                        })
                      }}
                    </q-tooltip>
                  </q-icon>
                </div>
                <div class="objective-slider__value text-caption text-primary">
                  {{ unitSliderLevels[cat] }}
                </div>
              </div>
              <q-slider
                v-model="unitSliderLevels[cat]"
                :min="1"
                :max="5"
                :step="1"
                snap
                dense
                track-color="grey-4"
                thumb-size="12px"
                track-size="2px"
              />
            </div>
          </div>
        </div>
      </section>
    </div>
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

.unit-controls {
  height: 100%;
  min-height: 620px;
  background: transparent;
  margin: 0;
  box-sizing: border-box;
  border-left: 1px solid rgba(0, 0, 0, 0.12);
}

.unit-controls__sliders {
  overflow: visible;
}

.unit-controls :deep(.q-slider__marker-labels),
.unit-controls :deep(.q-slider__markers) {
  display: none;
}

.unit-controls :deep(.q-slider) {
  margin-left: 6px;
  margin-right: 6px;
}

.unit-controls__scroll {
  overflow-y: auto;
  overflow-x: hidden;
  max-height: 520px;
}

/* Minimal override: allow per-category HEX colors for thumb + selection. */
.objective-slider :deep(.q-slider__selection),
.objective-slider :deep(.q-slider__selection-bar),
.objective-slider :deep(.q-slider__selection-area) {
  background: var(--cat-color) !important;
}

.objective-slider :deep(.q-slider__thumb) {
  background: var(--cat-color) !important;
  color: var(--cat-color) !important;
  border-radius: 999px !important;
}

.objective-slider__header {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: start;
  column-gap: 12px;
}

.objective-slider__label {
  min-width: 0;
  display: inline-flex;
  align-items: flex-start;
  gap: 6px;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.55;
}

.objective-slider__label-text {
  min-width: 0;
}

.objective-slider__label-info {
  flex: 0 0 auto;
  margin-top: 1px;
}

.objective-slider__value {
  font-variant-numeric: tabular-nums;
  text-align: right;
  line-height: 1.5;
}
</style>
