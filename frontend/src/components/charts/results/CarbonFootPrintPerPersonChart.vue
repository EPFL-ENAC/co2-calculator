<script setup lang="ts">
import { computed, ref, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import TooltipEcharts from './TooltipEcharts.vue';
import type { TooltipRow, TooltipState } from 'src/types/chartTooltip';
import type { EChartsOption, SeriesOption } from 'echarts';
import {
  buildChartDecal,
  CHART_CATEGORY_COLOR_SCHEMES,
  colors,
} from 'src/constant/charts';
import { useColorblindStore } from 'src/stores/colorblind';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';

import { useEchartsTooltip } from './useEchartsTooltip';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
]);

import { formatTonnesForChart } from 'src/utils/number';
import { usePrintMode } from 'src/composables/print/usePrintMode';
import { downloadEchartAsPng } from 'src/utils/chartDownload';

const props = defineProps<{
  perPersonBreakdown?: Record<string, number> | null;
  validatedCategories?: string[] | null;
  headcountValidated?: boolean;
  showValidationPlaceholder?: boolean;
  title?: string;
  viewAdditionalData?: boolean;
}>();

const { t } = useI18n();
const isPrintMode = usePrintMode();
const colorblindStore = useColorblindStore();
const isColorblind = computed(() => colorblindStore.enabled);
const toggleAdditionalData = ref(false);
const effectiveToggle = computed(
  () => props.viewAdditionalData ?? toggleAdditionalData.value,
);

const { tooltip, style, attach, emitTooltip } = useEchartsTooltip();

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

const SHOW_EPFL_REFERENCE_ROW = false;
const SHOW_OBJECTIVE_ROW = false;
const SHOW_OBJECTIVE_BAR = SHOW_OBJECTIVE_ROW;

// --- KEEP ALL YOUR EXISTING COMPUTEDS UNCHANGED ---

const validatedPPKeys = computed(() => {
  if (!props.validatedCategories) return new Set<string>();
  return new Set(props.validatedCategories);
});

const myUnitRow = computed<Record<string, unknown>>(() => {
  if (!props.perPersonBreakdown) {
    return { category: t('charts-my-unit-tick') };
  }
  return {
    category: t('charts-my-unit-tick'),
    ...props.perPersonBreakdown,
  };
});

const EPFL_REFERENCE_VALUES: Record<string, number> = {
  process_emissions: 2.5,
  buildings: 6.6,
  equipment: 4.4,
  research_facilities: 4.0,
  professional_travel: 14.7,
  purchases: 31.3,
  external_cloud_and_ai: 3.0,
  commuting: 8.8,
  food: 10.4,
  waste: 0.0,
  embodied_energy: 0.0,
};

const epflReferenceRow = computed<Record<string, unknown>>(() => {
  const row: Record<string, unknown> = { category: t('charts-epf-tick') };
  const validated = validatedPPKeys.value;
  for (const [key, val] of Object.entries(EPFL_REFERENCE_VALUES)) {
    if (validated.has(key)) {
      row[key] = val;
    }
  }
  return row;
});

const objectiveRow = computed<Record<string, unknown>>(() => ({
  category: t('charts-objective-tick'),
  objective2030: 12,
}));

const datasetSource = computed(() => {
  const baseData = [myUnitRow.value];
  if (SHOW_EPFL_REFERENCE_ROW) {
    baseData.push(epflReferenceRow.value);
  }
  if (SHOW_OBJECTIVE_ROW) {
    baseData.push(objectiveRow.value);
  }
  return baseData;
});

const additionalSeriesData = computed(() => {
  if (!effectiveToggle.value) return [];
  const encodeFor = (cat: string, val: string) =>
    isPrintMode.value ? { x: val, y: cat } : { x: cat, y: val };
  return [
    {
      name: t('charts-commuting-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'commuting'),
      itemStyle: {
        color: CHART_CATEGORY_COLOR_SCHEMES.value.commuting,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-food-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'food'),
      itemStyle: {
        color: colors.value.mint.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-waste-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'waste'),
      itemStyle: {
        color: colors.value.periwinkle.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-embodied-energy-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'embodied_energy'),
      itemStyle: {
        color: CHART_CATEGORY_COLOR_SCHEMES.value.embodied_energy,
      },
      label: {
        show: false,
      },
    },
  ];
});

function encodeFor(categoryAxis: string, valueAxis: string) {
  return isPrintMode.value
    ? { x: valueAxis, y: categoryAxis }
    : { x: categoryAxis, y: valueAxis };
}

const seriesArray = computed(() => {
  const barMaxWidth = isPrintMode.value ? 40 : undefined;
  return [
    {
      name: t('charts-process-emissions-category'),
      type: 'bar' as const,
      stack: 'total',
      barMaxWidth,
      encode: encodeFor('category', 'process_emissions'),
      itemStyle: {
        color: CHART_CATEGORY_COLOR_SCHEMES.value.process_emissions,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-buildings-energy-combustion-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'buildings_energy_combustion'),
      itemStyle: {
        color: CHART_CATEGORY_COLOR_SCHEMES.value.buildings_energy_combustion,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-buildings-room-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'buildings_room'),
      itemStyle: {
        color: CHART_CATEGORY_COLOR_SCHEMES.value.buildings_room,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('equipment-electric-consumption'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'equipment'),
      itemStyle: {
        color: CHART_CATEGORY_COLOR_SCHEMES.value.equipment,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('external-cloud-and-ai'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'external_cloud_and_ai'),
      itemStyle: {
        color: CHART_CATEGORY_COLOR_SCHEMES.value.external_cloud_and_ai,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('professional-travel'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'professional_travel'),
      itemStyle: {
        color: colors.value.babyBlue.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('purchase'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'purchases'),
      itemStyle: {
        color: colors.value.lightGreen.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('research-facilities'),
      type: 'bar' as const,
      stack: 'total',
      encode: encodeFor('category', 'research_facilities'),
      itemStyle: {
        color: colors.value.paleYellowGreen.darker,
      },
      label: {
        show: false,
      },
    },
    ...(SHOW_OBJECTIVE_BAR
      ? [
          {
            name: t('charts-objective-tick'),
            type: 'bar' as const,
            stack: 'total',
            encode: encodeFor('category', 'objective2030'),
            itemStyle: {
              color: colors.value.skyBlue.darker,
            },
            label: {
              show: false,
            },
          },
        ]
      : []),
    ...additionalSeriesData.value,
  ];
});

const chartTooltipOption = computed(() => {
  if (isPrintMode.value) return { show: false };

  function tooltipFormatter(params: unknown): string {
    const arr = Array.isArray(params) ? params : params ? [params] : [];
    if (!arr.length) {
      emitTooltip(null);
      return '';
    }

    const firstParam = arr[0] as Record<string, unknown>;
    const data = firstParam.data as Record<string, unknown> | undefined;
    const title = String(firstParam.axisValue ?? firstParam.name ?? '');

    const rows: TooltipRow[] = [];

    for (const param of [...arr].reverse()) {
      const p = param as Record<string, unknown>;
      const series = seriesArray.value.find((s) => s.name === p.seriesName);
      const key = series?.encode.y;
      const dataValue = Number(data?.[key]) || 0;
      if (dataValue > 0 && series) {
        rows.push({
          label: series.name,
          value: formatTonnesForChart(dataValue),
          color: (series.itemStyle?.color as string) ?? '#888',
        });
      }
    }

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

const chartXAxisOption = computed(() => {
  if (isPrintMode.value) {
    return {
      type: 'value' as const,
      name: t('tco2eq'),
      nameLocation: 'middle' as const,
      nameGap: 30,
      nameTextStyle: { fontSize: 11, fontWeight: 'bold' as const },
      axisLabel: { formatter: '{value}' },
    };
  }
  return {
    type: 'category' as const,
    axisLabel: { interval: 0, rotate: 45, fontSize: 11 },
  };
});

const chartYAxisOption = computed(() => {
  if (isPrintMode.value) {
    return {
      type: 'category' as const,
      axisLabel: { fontSize: 11 },
      axisTick: { alignWithLabel: true },
    };
  }
  return {
    type: 'value' as const,
    name: t('tco2eq'),
    nameLocation: 'middle' as const,
    nameGap: 40,
    nameRotate: 90,
    nameTextStyle: { fontSize: 11, fontWeight: 'bold' as const },
    axisLabel: { formatter: '{value}' },
  };
});

const chartGraphicOption = computed(() => []);

const chartOption = computed((): EChartsOption => {
  return {
    tooltip: chartTooltipOption.value,
    grid: chartGridOption.value,
    xAxis: chartXAxisOption.value,
    yAxis: chartYAxisOption.value,
    graphic: chartGraphicOption.value,
    aria: {
      enabled: isColorblind.value,
      decal: buildChartDecal(isColorblind.value),
    },
    dataset: {
      dimensions: [
        'category',
        'process_emissions',
        'buildings_room',
        'buildings_energy_combustion',
        'equipment',
        'research_facilities',
        'professional_travel',
        'purchases',
        'external_cloud_and_ai',
        'commuting',
        'food',
        'waste',
        'embodied_energy',
        ...(SHOW_OBJECTIVE_BAR ? ['objective2030'] : []),
      ],
      source: datasetSource.value as Array<Record<string, unknown>>,
    },
    series: seriesArray.value as SeriesOption[],
  };
});

const downloadPNG = () =>
  downloadEchartAsPng(chartRef.value?.chart, 'carbon-footprint-per-person');

const downloadCSV = () => {
  const escape = (v: unknown) => {
    const s = String(v ?? '');
    return /[,"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };

  const headers = [
    ...new Set(datasetSource.value.flatMap((item) => Object.keys(item))),
  ].sort((a, b) =>
    a === 'category' ? -1 : b === 'category' ? 1 : a.localeCompare(b),
  );

  const csv = [
    headers.map(escape).join(','),
    ...datasetSource.value.map((item) =>
      headers.map((key) => escape(item[key])).join(','),
    ),
  ].join('\n');

  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = `carbon-footprint-per-person-${new Date().toISOString().replace(/[:.]/g, '-')}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
};
</script>

<template>
  <q-card
    flat
    class="container container--pa-none full-width"
    :class="{ 'container--print': isPrintMode }"
  >
    <q-card-section
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

    <template v-if="headcountValidated || showValidationPlaceholder === false">
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
          icon="o_download"
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
          icon="o_download"
          :label="$t('common_download_as_csv')"
          size="xs"
          dense
          class="text-weight-bold q-px-sm"
          @click="downloadCSV"
        />
      </q-card-section>
    </template>

    <template v-else>
      <q-card-section class="col validation-placeholder">
        <div class="validation-required-card">
          <div class="validation-required-card__content">
            <q-icon name="o_info" size="md" color="accent" class="q-mb-md" />
            <div class="text-h6 text-weight-medium text-center q-mb-sm">
              {{
                $t('results_validate_module_title', { module: $t('headcount') })
              }}
            </div>
            <div class="text-body2 text-secondary text-center">
              {{ $t('results_validate_module_message') }}
            </div>
          </div>
        </div>
      </q-card-section>
    </template>
  </q-card>
</template>

<style scoped lang="scss">
.container--pa-none {
  display: flex;
  flex-direction: column;
}

.chart {
  width: 100%;
  min-height: 420px;
}

.chart--print {
  min-height: unset;
  height: 120px !important;
}

.validation-placeholder {
  flex: 1;
  display: flex;
}

.validation-required-card {
  flex: 1;
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
