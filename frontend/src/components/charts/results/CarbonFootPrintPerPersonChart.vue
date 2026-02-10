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

const props = defineProps<{
  viewUncertainties?: boolean;
}>();

const { t } = useI18n();
const toggleAdditionalData = ref(false);

const datasetSource = computed(() => {
  const baseData = [
    {
      category: t('charts-my-unit-tick'),
      unitGas: 2.5,
      infrastructureGas: 2.0,
      infrastructure: 8.3,
      equipment: 5.5,
      itInfrastructure: 5.0,
      professionalTravel: 18.4,
      purchases: 39.1,
      researchCoreFacilities: 3.0,
      commuting: 11.0,
      food: 13.0,
      waste: 0.0,
      greyEnergy: 0.0,
      stdDev: 10,
    },
    {
      category: t('charts-epf-tick'),
      unitGas: 2.0,
      infrastructureGas: 1.6,
      infrastructure: 6.6,
      equipment: 4.4,
      itInfrastructure: 4.0,
      professionalTravel: 14.7,
      purchases: 31.3,
      researchCoreFacilities: 3.0,
      commuting: 8.8,
      food: 10.4,
      waste: 0.0,
      greyEnergy: 0.0,
      stdDev: 10,
    },
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
    'unitGas',
    'infrastructureGas',
    'infrastructure',
    'equipment',
    'itInfrastructure',
    'professionalTravel',
    'purchases',
    'researchCoreFacilities',
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
      name: t('charts-unit-gas-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'unitGas',
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
        color: colors.value.peach.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-infrastructure-gas-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'infrastructureGas',
      },
      itemStyle: {
        color: colors.value.apricot.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-infrastructure-category'),
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
      name: t('charts-equipment-category'),
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
      name: t('charts-it-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'itInfrastructure',
      },
      itemStyle: {
        color: colors.value.lavender.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-professional-travel-category'),
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
      name: t('charts-purchases-category'),
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
      name: t('charts-research-core-facilities-category'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'researchCoreFacilities',
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
            tooltip += `${p.marker || ''} ${series?.name || p.seriesName || ''}: <strong>${dataValue.toFixed(1)} </strong><br/>`;
            total += dataValue;
          }
        });

        let totalDisplay = total.toFixed(1);
        if (showUncertainties && data) {
          const stdDev = Number(data.stdDev) || 0;
          if (stdDev > 0)
            totalDisplay = `${total.toFixed(1)} ± ${stdDev.toFixed(1)}`;
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
      {
        type: 'rect',
        left: '335px',
        top: '0px',
        shape: {
          width: 1,
          height: 420,
        },
        style: {
          fill: new graphic.LinearGradient(0, 0, 0, 1, [
            {
              offset: 0,
              color: 'rgba(0,0,0)',
            },
            {
              offset: 1,
              color: 'rgba(240,240,240,0.1)',
            },
          ]),
        },
        z: 100,
      },
    ],
    dataset: {
      dimensions: [
        'category',
        'unitGas',
        'infrastructureGas',
        'infrastructure',
        'equipment',
        'itInfrastructure',
        'professionalTravel',
        'purchases',
        'researchCoreFacilities',
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

      <div>
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
        v-model="toggleAdditionalData"
        :label="$t('results_module_carbon_toggle_additional_data')"
        size="xs"
        color="accent"
      />
    </q-card-section>
    <q-card-section class="chart-container flex justify-center items-center">
      <v-chart ref="chartRef" class="chart" autoresize :option="chartOption" />
    </q-card-section>
  </q-card>
</template>

<style scoped>
.chart {
  width: 500px;
  min-height: 500px;
}
</style>
