<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import { graphic } from 'echarts';
import { colors } from 'src/constant/charts';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
]);

import { formatTonnesForChart } from 'src/utils/number';

const props = defineProps<{
  perPersonBreakdown?: Record<string, number> | null;
  validatedCategories?: string[] | null;
  headcountValidated?: boolean;
  showValidationPlaceholder?: boolean;
  title?: string;
}>();

const { t } = useI18n();
const toggleAdditionalData = ref(false);
const SHOW_EPFL_REFERENCE_ROW = false;
const SHOW_OBJECTIVE_ROW = false;
const SHOW_OBJECTIVE_BAR = SHOW_OBJECTIVE_ROW;

const validatedPPKeys = computed(() => {
  if (!props.validatedCategories) return new Set<string>();
  const keys = new Set(props.validatedCategories);

  // Per-person data merges both buildings categories into one key.
  if (keys.has('buildings_room') || keys.has('buildings_energy_combustion')) {
    keys.add('buildings');
  }

  return new Set(keys);
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
  if (!toggleAdditionalData.value) return [];

  return [
    {
      name: t('charts-commuting-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'commuting',
      },
      itemStyle: {
        color: colors.value.skyBlue.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-food-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'food',
      },
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
      encode: {
        x: 'category',
        y: 'waste',
      },
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
      encode: {
        x: 'category',
        y: 'embodied_energy',
      },
      itemStyle: {
        color: colors.value.skyBlue.darker,
      },
      label: {
        show: false,
      },
    },
  ];
});

const chartOption = computed((): EChartsOption => {
  const seriesArray = [
    {
      name: t('charts-process-emissions-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'process_emissions',
      },
      itemStyle: {
        color: colors.value.apricot.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('buildings'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'buildings',
      },
      itemStyle: {
        color: colors.value.lilac.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('equipment-electric-consumption'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'equipment',
      },
      itemStyle: {
        color: colors.value.mauve.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('research-facilities'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'research_facilities',
      },
      itemStyle: {
        color: colors.value.paleYellowGreen.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('professional-travel'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'professional_travel',
      },
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
      encode: {
        x: 'category',
        y: 'purchases',
      },
      itemStyle: {
        color: colors.value.lightGreen.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('external-cloud-and-ai'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'external_cloud_and_ai',
      },
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
            encode: {
              x: 'category',
              y: 'objective2030',
            },
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

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },

      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : params ? [params] : [];
        if (!arr.length) return '';

        const firstParam = arr[0] as Record<string, unknown>;
        const data = firstParam.data as Record<string, unknown> | undefined;
        const name = (firstParam.axisValue || firstParam.name || '') as string;

        let total = 0;
        let tooltip = `<strong>${name}</strong><br/>`;

        arr.reverse().forEach((param) => {
          const p = param as Record<string, unknown>;
          const series = seriesArray.find((s) => s.name === p.seriesName);
          const key = series?.encode.y;
          const dataValue = Number(data?.[key]) || 0;

          if (dataValue > 0) {
            tooltip += `${p.marker || ''} ${series?.name || p.seriesName || ''}: <strong>${formatTonnesForChart(dataValue)} </strong><br/>`;
            total += dataValue;
          }
        });

        const totalDisplay = formatTonnesForChart(total);

        return `${tooltip}<hr style="margin: 4px 0"/>Total: <strong>${totalDisplay}</strong>`;
      },
    },

    grid: {
      left: '5%',
      right: '4%',
      top: 80,
      bottom: '0%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      axisLabel: {
        interval: 0,
        rotate: 45,
        fontSize: 11,
      },
    },
    yAxis: {
      type: 'value',
      name: t('tco2eq'),
      nameLocation: 'middle',
      nameGap: 40,
      nameRotate: 90,
      nameTextStyle: {
        fontSize: 11,
        fontWeight: 'bold',
      },
      axisLabel: {
        formatter: '{value}',
      },
    },
    graphic: [
      {
        type: 'rect',
        left: '46px',
        top: '15px',
        shape: {
          width: 500,
          height: 300,
        },
        style: {
          fill: new graphic.LinearGradient(0, 0, 0, 1, [
            {
              offset: 0,
              color: 'rgba(240,240,240,0.9)',
            },
            {
              offset: 1,
              color: 'rgba(240,240,240,0.1)',
            },
          ]),
        },
      },
    ],
    dataset: {
      dimensions: [
        'category',
        'process_emissions',
        'buildings',
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
    series: seriesArray as echarts.SeriesOption[],
  };
});

const chartRef = ref<InstanceType<typeof VChart>>();

const downloadPNG = async () => {
  const chart = chartRef.value?.chart;
  if (!chart) return;

  try {
    // Wait a bit to ensure no animation in the image
    await new Promise((resolve) => setTimeout(resolve, 200));

    const url = chart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff',
    });

    const link = document.createElement('a');
    link.href = url;
    link.download = `carbon-footprint-per-person-${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } catch (error) {
    console.error('Error downloading chart:', error);
  }
};

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
  <q-card flat class="container container--pa-none full-width">
    <q-card-section class="flex justify-between items-center">
      <div>
        <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
          {{
            props.title ?? $t('results_carbon_footprint_per_FTE_no_headcount')
          }}
        </span>
      </div>

      <q-checkbox
        v-if="headcountValidated"
        v-model="toggleAdditionalData"
        :label="$t('results_module_carbon_toggle_additional_data')"
        size="xs"
        color="accent"
      />
    </q-card-section>

    <template v-if="headcountValidated || showValidationPlaceholder === false">
      <q-card-section class="chart-container flex justify-center items-center">
        <v-chart
          ref="chartRef"
          class="chart"
          autoresize
          :option="chartOption"
        />
      </q-card-section>

      <q-card-actions
        v-if="headcountValidated"
        align="center"
        class="q-px-md q-pb-md q-pt-none"
      >
        <q-btn
          unelevated
          no-caps
          outline
          icon="o_download"
          :label="$t('common_download_as_png')"
          size="sm"
          class="text-weight-medium q-mr-xs"
          @click="downloadPNG"
        />
        <q-btn
          unelevated
          no-caps
          outline
          icon="o_download"
          :label="$t('common_download_as_csv')"
          size="sm"
          class="text-weight-medium"
          @click="downloadCSV"
        />
      </q-card-actions>
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
  width: 200px;
  min-height: 500px;
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
