<script setup lang="ts">
import { computed, ref, nextTick } from 'vue';
import {
  outlinedDownload,
  outlinedInfo,
} from '@quasar/extras/material-icons-outlined';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import TooltipEcharts from './TooltipEcharts.vue';
import type { TooltipRow, TooltipState } from '@/types/chartTooltip';
import type { EChartsOption, SeriesOption } from 'echarts';
import { getCssVar } from 'quasar';
import {
  buildChartDecal,
  CHART_CATEGORY_COLOR_SCHEMES,
  isHiddenResultsCategory,
  YEARS_DECAL,
} from '@/constant/charts';
import type { PerPersonRow } from '@/utils/plannerPerFte';
import { useColorblindStore } from '@/stores/colorblind';
import { useModuleCategoriesAvailability } from '@/composables/results/useModuleCategoriesAvailability';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';

import { useEchartsTooltip } from './useEchartsTooltip';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
]);

import { formatTonnesForChart } from '@/utils/number';
import { usePrintMode } from '@/composables/print/usePrintMode';
import { downloadEchartAsPng } from '@/utils/chartDownload';
import { downloadCsv, escapeCsvValue } from '@/utils/csvDownload';

const props = withDefaults(
  defineProps<{
    perPersonBreakdown?: Record<string, number> | null;
    /**
     * Several bars instead of the single "My unit" one, e.g. the Planner's

     */
    rows?: PerPersonRow[] | null;
    validatedCategories?: string[] | null;
    headcountValidated?: boolean;
    showValidationPlaceholder?: boolean;
    /**
     * Placeholder wording when headcount is missing: the Calculator asks to
     * validate the module, the simulators (no validation step) to fill it in.
     */
    placeholderVariant?: 'validate' | 'add';
    title?: string;
    viewAdditionalData?: boolean;
    /**
     * Hide categories whose module/submodule is deactivated in the current
     * year's back-office config. Defaults on for single-year workspace
     * contexts; callers that aggregate data across multiple years/units with
     * no single "current year" config loaded (e.g. the back-office Reporting
     * page) must opt out — yearConfigStore only ever holds one year's
     * config, so applying it there would silently hide every category or
     * apply an arbitrary year's rules to the aggregate.
     */
    enforceModuleActivation?: boolean;
  }>(),
  {
    perPersonBreakdown: null,
    rows: null,
    validatedCategories: null,
    placeholderVariant: 'validate',
    title: undefined,
    enforceModuleActivation: true,
  },
);

const { t } = useI18n();
const isPrintMode = usePrintMode();
const colorblindStore = useColorblindStore();
const isColorblind = computed(() => colorblindStore.enabled);
const { isCategoryModuleActive } = useModuleCategoriesAvailability();

function isCategoryVisible(categoryKey: string): boolean {
  if (isHiddenResultsCategory(categoryKey)) return false;
  if (props.enforceModuleActivation) {
    return isCategoryModuleActive(categoryKey);
  }
  return true;
}
const toggleAdditionalData = ref(false);
const effectiveToggle = computed(
  () => props.viewAdditionalData ?? toggleAdditionalData.value,
);

const { tooltip, style, attach, emitTooltip } = useEchartsTooltip();

const showChart = computed(
  () => props.headcountValidated || props.showValidationPlaceholder === false,
);

const chartRef = ref<InstanceType<typeof VChart>>();

const onChartReady = async () => {
  await nextTick();

  const chart = chartRef.value?.chart;

  if (!chart) {
    console.warn('ECharts instance not ready yet');
    return;
  }

  attach(chart);
};

type CategoryKey = keyof typeof CHART_CATEGORY_COLOR_SCHEMES.value;

const MAIN_SERIES: { key: CategoryKey; labelKey: string }[] = [
  { key: 'process_emissions', labelKey: 'charts-process-emissions-category' },
  {
    key: 'buildings_energy_combustion',
    labelKey: 'charts-buildings-energy-combustion-category',
  },
  { key: 'buildings_room', labelKey: 'charts-buildings-room-category' },
  { key: 'equipment', labelKey: 'equipment' },
  { key: 'external_cloud_and_ai', labelKey: 'external-cloud-and-ai' },
  { key: 'professional_travel', labelKey: 'professional-travel' },
  { key: 'purchases', labelKey: 'purchase' },
  { key: 'research_facilities', labelKey: 'research-facilities' },
];
const ADDITIONAL_SERIES: { key: CategoryKey; labelKey: string }[] = [
  { key: 'commuting', labelKey: 'charts-commuting-category' },
  { key: 'food', labelKey: 'charts-food-category' },
  { key: 'waste', labelKey: 'charts-waste-category' },
  { key: 'embodied_energy', labelKey: 'charts-embodied-energy-category' },
];

/** The bars: the single unit one, or the caller's rows (#2071). */
const chartRows = computed<PerPersonRow[]>(
  () =>
    props.rows ?? [
      {
        label: t('charts-my-unit-tick'),
        perPersonBreakdown: props.perPersonBreakdown ?? {},
      },
    ],
);

const visibleSeriesDefs = computed(() =>
  [...MAIN_SERIES, ...(effectiveToggle.value ? ADDITIONAL_SERIES : [])].filter(
    (def) => isCategoryVisible(def.key),
  ),
);

// Every bar sits on the one "Total" tick: rows become side-by-side stacks
// named after their label, so the legend and the tooltip tell them apart the
// way PlannerGrantComparisonChart does (its series are named per view too).
const seriesArray = computed(() =>
  chartRows.value.flatMap((row, rowIdx) =>
    visibleSeriesDefs.value.map((def) => ({
      name: row.label,
      id: `${rowIdx}:${def.key}`,
      key: def.key,
      categoryLabel: t(def.labelKey),
      type: 'bar' as const,
      stack: row.label,
      barMaxWidth: isPrintMode.value ? 40 : undefined,
      itemStyle: {
        color: CHART_CATEGORY_COLOR_SCHEMES.value[def.key],
        // Same hatch as PlannerGrantComparisonChart's "Detailed per year" bars.
        ...(row.hatched ? { decal: YEARS_DECAL } : {}),
      },
      label: { show: false },
      data: [row.perPersonBreakdown[def.key] ?? 0],
    })),
  ),
);

// Same swatches as PlannerGrantComparisonChart's legend.
const chartLegendOption = computed(() => ({
  show: chartRows.value.length > 1 && !isPrintMode.value,
  top: 0,
  data: chartRows.value.map((row) => ({
    name: row.label,
    itemStyle: {
      color: getCssVar('info') ?? undefined,
      ...(row.hatched ? { decal: YEARS_DECAL } : {}),
    },
  })),
}));

const chartTooltipOption = computed(() => {
  if (isPrintMode.value) return { show: false };

  function tooltipFormatter(params: unknown): string {
    const arr = Array.isArray(params) ? params : params ? [params] : [];
    if (!arr.length) {
      emitTooltip(null);
      return '';
    }

    const firstParam = arr[0] as Record<string, unknown>;
    const title = String(firstParam.axisValue ?? firstParam.name ?? '');
    const byId = new Map(seriesArray.value.map((s) => [s.id, s]));
    const sectioned = chartRows.value.length > 1;

    // One block per bar: its label and total, then its categories, the
    // largest segment (top of the stack) first.
    const rows: TooltipRow[] = chartRows.value.flatMap((row, rowIdx) => {
      const items = [...arr]
        .reverse()
        .map((param) => {
          const p = param as Record<string, unknown>;
          const series = byId.get(String(p.seriesId ?? ''));
          const value = Number(p.value) || 0;
          return series && series.id.startsWith(`${rowIdx}:`) && value > 0
            ? { series, value }
            : null;
        })
        .filter((item): item is NonNullable<typeof item> => item !== null);
      const total = items.reduce((sum, item) => sum + item.value, 0);
      return [
        ...(sectioned
          ? [
              {
                label: row.label,
                value: formatTonnesForChart(total),
                heading: true,
              },
            ]
          : []),
        ...items.map((item) => ({
          label: item.series.categoryLabel,
          value: formatTonnesForChart(item.value),
          color: item.series.itemStyle.color,
        })),
      ];
    });

    const state: TooltipState = { title, rows };
    emitTooltip(state);
    return '';
  }

  return {
    trigger: 'axis' as const,
    axisPointer: { type: 'shadow' as const },
    formatter: tooltipFormatter,
  };
});

const chartGridOption = computed(() => {
  if (isPrintMode.value) {
    return {
      left: '10%',
      right: '4%',
      top: 10,
      bottom: 30,
      containLabel: true,
    };
  }
  return { left: 65, right: '4%', top: 80, bottom: '0%', containLabel: true };
});

const categoryAxisOption = computed(() => ({
  type: 'category' as const,
  data: [t('charts-my-unit-tick')],
  axisLabel: isPrintMode.value
    ? { fontSize: 11 }
    : { interval: 0, rotate: 45, fontSize: 11 },
  ...(isPrintMode.value ? { axisTick: { alignWithLabel: true } } : {}),
}));

const valueAxisOption = computed(() => ({
  type: 'value' as const,
  name: t('tco2eq'),
  nameLocation: 'middle' as const,
  nameGap: isPrintMode.value ? 30 : 40,
  ...(isPrintMode.value ? {} : { nameRotate: 90 }),
  nameTextStyle: { fontSize: 11, fontWeight: 'bold' as const },
  axisLabel: { formatter: '{value}' },
}));

// Print reports lay the bars horizontally: the axes swap roles.
const chartOption = computed((): EChartsOption => {
  return {
    tooltip: chartTooltipOption.value,
    legend: chartLegendOption.value,
    grid: chartGridOption.value,
    xAxis: isPrintMode.value ? valueAxisOption.value : categoryAxisOption.value,
    yAxis: isPrintMode.value ? categoryAxisOption.value : valueAxisOption.value,
    aria: {
      enabled: isColorblind.value,
      decal: buildChartDecal(isColorblind.value),
    },
    series: seriesArray.value as SeriesOption[],
  };
});

const downloadPNG = () =>
  downloadEchartAsPng(chartRef.value?.chart, 'carbon-footprint-per-person');

const downloadCSV = () => {
  const escape = escapeCsvValue;
  const keys = visibleSeriesDefs.value
    .map((def) => def.key)
    .sort((a, b) => a.localeCompare(b));
  const headers = ['category', ...keys];

  const csv = [
    headers.map(escape).join(','),
    ...chartRows.value.map((row) =>
      [
        escape(row.label),
        ...keys.map((key) => escape(row.perPersonBreakdown[key] ?? '')),
      ].join(','),
    ),
  ].join('\n');

  downloadCsv(
    csv,
    `carbon-footprint-per-person-${new Date().toISOString().replace(/[:.]/g, '-')}.csv`,
  );
};
</script>

<template>
  <q-card
    flat
    class="container container--pa-none full-width"
    :class="{ 'container--print': isPrintMode }"
  >
    <q-card-section
      v-if="showChart"
      class="flex justify-between items-center"
      :class="{ 'q-pb-none': isPrintMode }"
    >
      <div>
        <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
          {{
            props.title ?? $t('results_carbon_footprint_per_FTE_no_headcount')
          }}
        </span>
      </div>

      <div v-if="!isPrintMode">
        <q-checkbox
          v-if="
            props.viewAdditionalData === undefined &&
            (headcountValidated || props.showValidationPlaceholder === false)
          "
          v-model="toggleAdditionalData"
          :label="$t('results_module_carbon_toggle_additional_data')"
          size="xs"
          color="accent"
        />
      </div>
    </q-card-section>

    <template v-if="showChart">
      <q-card-section class="chart-container flex justify-center items-center">
        <v-chart
          ref="chartRef"
          :key="colorblindStore.enabled ? 'cb' : 'default'"
          :class="['chart', { 'chart--print': isPrintMode }]"
          autoresize
          :option="chartOption"
          @vue:mounted="onChartReady"
        />
        <Teleport to="body">
          <tooltip-echarts
            v-if="tooltip.visible"
            :tooltip-state="tooltip.data"
            :style="style"
          />
        </Teleport>
      </q-card-section>
      <q-separator v-if="!isPrintMode && headcountValidated" />
      <q-card-section
        v-if="!isPrintMode && headcountValidated"
        class="flex justify-start q-gutter-sm"
      >
        <q-btn
          unelevated
          no-caps
          outline
          :icon="outlinedDownload"
          :label="$t('common_download_as_png')"
          size="xs"
          dense
          class="text-weight-bold q-px-sm"
          @click="downloadPNG"
        />
        <q-btn
          unelevated
          no-caps
          outline
          :icon="outlinedDownload"
          :label="$t('common_download_as_csv')"
          size="xs"
          dense
          class="text-weight-bold q-px-sm"
          @click="downloadCSV"
        />
      </q-card-section>
    </template>

    <!-- Replaces the whole card, title included, like the Results page's
         own placeholder beside its main chart. -->
    <div v-else class="validation-required-card">
      <div class="validation-required-card__content">
        <q-icon :name="outlinedInfo" size="md" color="info" class="q-mb-md" />
        <div class="text-h6 text-weight-medium text-center q-mb-sm">
          {{
            $t(
              placeholderVariant === 'add'
                ? 'results_add_module_title'
                : 'results_validate_module_title',
              { module: $t('headcount') },
            )
          }}
        </div>
        <div class="text-body2 text-secondary text-center">
          {{
            $t(
              placeholderVariant === 'add'
                ? 'results_add_module_message'
                : 'results_validate_module_message',
            )
          }}
        </div>
      </div>
    </div>
  </q-card>
</template>

<style scoped lang="scss">
.container--pa-none {
  display: flex;
  flex-direction: column;
  // Fill the side column beside the main chart, so the placeholder card
  // spans the same height (charts-grid, #2071).
  flex: 1;
}

/* #2027: a definite height, not min-height. vue-echarts 8.1.0 renders an
   <x-vue-echarts> custom element carrying its own `height: 100%`, and its
   resize observer skips any resize where a dimension is 0 — so a chart that
   measures zero once at init stays a zero-height canvas forever: fully
   populated, no error, nothing drawn. Every chart that kept working through
   the 8.0.1 -> 8.1.0 bump sets a definite height; the two that broke were the
   two using min-height. Keep it definite. */
.chart {
  width: 100%;
  height: 420px;
}

.chart--print {
  height: 120px !important;
}

.validation-required-card {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  background-color: rgba(0, 0, 0, 0.02);
  border: 1px dashed rgba(0, 0, 0, 0.12);

  &__content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    padding: 3rem;
  }
}
</style>
