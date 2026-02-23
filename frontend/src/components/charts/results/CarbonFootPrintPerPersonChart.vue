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
  viewUncertainties?: boolean;
  perPersonBreakdown?: Record<string, number> | null;
  validatedCategories?: string[] | null;
  headcountValidated?: boolean;
}>();

const { t } = useI18n();
const toggleAdditionalData = ref(false);

const CATEGORY_TO_PP_KEYS: Record<string, string[]> = {
  'Process Emissions': ['processEmissions'],
  'Buildings energy consumption': ['infrastructure'],
  'Buildings room': ['infrastructure'],
  Equipment: ['equipment'],
  'External cloud & AI': ['externalCloudAndAI'],
  Purchases: ['purchases'],
  'Research facilities': ['researchFacilities'],
  'Professional travel': ['professionalTravel'],
  Commuting: ['commuting'],
  Food: ['food'],
  Waste: ['waste'],
  'Grey Energy': ['greyEnergy'],
};

const validatedPPKeys = computed(() => {
  if (!props.validatedCategories) return new Set<string>();
  const keys = new Set<string>();
  for (const cat of props.validatedCategories) {
    for (const k of CATEGORY_TO_PP_KEYS[cat] ?? []) {
      keys.add(k);
    }
  }
  return keys;
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
  processEmissions: 2.5,
  infrastructure: 6.6,
  equipment: 4.4,
  researchFacilities: 4.0,
  professionalTravel: 14.7,
  purchases: 31.3,
  externalCloudAndAI: 3.0,
  commuting: 8.8,
  food: 10.4,
  waste: 0.0,
  greyEnergy: 0.0,
};

const epflReferenceRow = computed<Record<string, unknown>>(() => {
  const row: Record<string, unknown> = { category: t('charts-epf-tick') };
  const validated = validatedPPKeys.value;
  for (const [key, val] of Object.entries(EPFL_REFERENCE_VALUES)) {
    if (validated.has(key)) {
      row[key] = val;
    }
  }
  row.stdDev = 10;
  return row;
});

const datasetSource = computed(() => {
  const baseData = [
    myUnitRow.value,
    epflReferenceRow.value,
    {
      category: t('charts-objective-tick'),
      objective2030: 12,
      stdDev: 5,
    },
  ];
  return baseData;
});

const allValueKeys = computed(() => {
  const baseKeys = [
    'processEmissions',
    'infrastructure',
    'equipment',
    'researchFacilities',
    'professionalTravel',
    'purchases',
    'externalCloudAndAI',
  ];

  if (toggleAdditionalData.value) {
    return [
      ...baseKeys,
      'commuting',
      'food',
      'waste',
      'greyEnergy',
      'objective2030',
    ];
  }
  return baseKeys;
});

const markLineData = computed(() => {
  if (!props.viewUncertainties) return [];

  return datasetSource.value
    .map((item, index) => {
      const total =
        allValueKeys.value.reduce(
          (sum, key) => sum + (Number(item[key]) || 0),
          0,
        ) + (Number(item.objective2030) || 0);

      const stdDev = Number(item.stdDev) || 0;

      if (total <= 0 || stdDev <= 0) return null;

      return [
        { xAxis: index, yAxis: total + stdDev },
        { xAxis: index, yAxis: Math.max(0, total - stdDev) },
      ];
    })
    .filter((item) => item !== null);
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
      name: t('charts-grey-energy-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'greyEnergy',
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
  const showUncertainties = props.viewUncertainties ?? false;
  const seriesArray = [
    {
      name: t('charts-process-emissions-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'processEmissions',
      },
      markLine: {
        silent: true,
        symbol: ['none', 'none'],
        lineStyle: {
          color: '#333',
          width: 1.5,
          type: 'solid' as const,
        },
        data: markLineData.value,
      },
      itemStyle: {
        color: colors.value.apricot.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('infrastructure'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'infrastructure',
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
      name: t('internal-services'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'researchFacilities',
      },
      itemStyle: {
        color: colors.value.lavender.darker,
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
        y: 'professionalTravel',
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
        y: 'externalCloudAndAI',
      },
      itemStyle: {
        color: colors.value.paleYellowGreen.darker,
      },
      label: {
        show: false,
      },
    },
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

        let totalDisplay = formatTonnesForChart(total);
        if (showUncertainties && data) {
          const stdDev = Number(data.stdDev) || 0;
          if (stdDev > 0)
            totalDisplay = `${formatTonnesForChart(total)} ± ${formatTonnesForChart(stdDev)}`;
        }

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
      nameGap: 30,
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
        'processEmissions',
        'infrastructure',
        'equipment',
        'researchFacilities',
        'professionalTravel',
        'purchases',
        'externalCloudAndAI',
        'commuting',
        'food',
        'waste',
        'greyEnergy',
        'objective2030',
        'stdDev',
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
  <q-card flat class="container container--pa-none">
    <q-card-section class="flex justify-between items-center">
      <div>
        <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
          {{ $t('results_carbon_footprint_per_person_title') }}
        </span>
      </div>

      <div v-if="headcountValidated">
        <q-btn
          unelevated
          no-caps
          outline
          icon="o_download"
          :label="$t('common_download_as_png')"
          size="sm"
          class="text-weight-medium q-mr-sm"
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
      </div>
      <q-checkbox
        v-if="headcountValidated"
        v-model="toggleAdditionalData"
        :label="$t('results_module_carbon_toggle_additional_data')"
        size="xs"
        color="accent"
      />
    </q-card-section>

    <template v-if="headcountValidated">
      <q-card-section class="chart-container flex justify-center items-center">
        <v-chart
          ref="chartRef"
          class="chart"
          autoresize
          :option="chartOption"
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
  width: 500px;
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
