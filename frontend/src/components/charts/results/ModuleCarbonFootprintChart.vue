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

import type { EmissionBreakdownResponse } from 'src/stores/modules';

const props = defineProps<{
  viewUncertainties?: boolean;
  breakdownData?: EmissionBreakdownResponse | null;
}>();

const { t } = useI18n();
const toggleAdditionalData = ref(false);

const additionalDataConfig = computed(() => {
  if (toggleAdditionalData.value) {
    return {
      scope2RectWidth: 55,
      scope3RectLeft: 101,
      scope3RectWidth: 233,
      scope3TextLeft: 111,
      estimatedRectLeft: 334,
      estimatedText: t('charts-additional-category'),
    };
  }

  return {
    scope2RectWidth: 82,
    scope3RectLeft: 128,
    scope3RectWidth: 500,
    scope3TextLeft: 138,
    estimatedRectLeft: 0,
    estimatedText: '',
  };
});

const CATEGORY_LABEL_MAP: Record<string, string> = {
  'Building': 'infrastructure',
  'Equipment': 'equipment-electric-consumption',
  'IT Infrastructure': 'internal-services',
  'Professional Travel': 'professional-travel',
  'Purchases': 'purchase',
  'Research Core Facilities': 'external-cloud-and-ai',
  'Commuting': 'charts-commuting-category',
  'Food': 'charts-food-category',
  'Waste': 'charts-waste-category',
  'Grey Energy': 'charts-grey-energy-category',
};

function translateCategory(entry: Record<string, unknown>): Record<string, unknown> {
  const cat = entry.category as string;
  const i18nKey = CATEGORY_LABEL_MAP[cat];
  return { ...entry, category: i18nKey ? t(i18nKey) : cat };
}

const datasetSource = computed(() => {
  if (!props.breakdownData) return [];

  const baseData = props.breakdownData.module_breakdown.map(translateCategory);

  if (toggleAdditionalData.value) {
    const additionalData = props.breakdownData.additional_breakdown.map(translateCategory);
    return [...baseData, ...additionalData];
  }
  return baseData;
});

const allValueKeys = computed(() => {
  const baseKeys = [
    'energy',
    'scientific', 'it', 'other',
    'plane', 'train',
    'stockage', 'virtualisation', 'calcul', 'ai_provider',
  ];

  if (toggleAdditionalData.value) {
    return [...baseKeys, 'commuting', 'food', 'waste', 'greyEnergy'];
  }
  return baseKeys;
});

const allStdDevKeys = computed(() => {
  const baseKeys = [
    'energyStdDev',
    'scientificStdDev', 'itStdDev', 'otherStdDev',
    'planeStdDev', 'trainStdDev',
    'stockageStdDev', 'virtualisationStdDev', 'calculStdDev', 'ai_providerStdDev',
  ];

  if (toggleAdditionalData.value) {
    return [
      ...baseKeys,
      'commutingStdDev',
      'foodStdDev',
      'wasteStdDev',
      'greyEnergyStdDev',
    ];
  }
  return baseKeys;
});

const markLineData = computed(() => {
  const showUncertainties = props.viewUncertainties ?? false;
  if (!showUncertainties) return [];

  return datasetSource.value
    .map((item, i) => {
      const total = allValueKeys.value.reduce(
        (sum, k) => sum + (Number(item[k]) || 0),
        0,
      );
      if (total <= 0) return null;
      const stdDev = Math.sqrt(
        allStdDevKeys.value.reduce(
          (sum, k) => sum + Math.pow(Number(item[k]) || 0, 2),
          0,
        ),
      );
      return [
        { xAxis: i, yAxis: total + stdDev },
        { xAxis: i, yAxis: Math.max(0, total - stdDev) },
      ] as const;
    })
    .filter(
      (
        item,
      ): item is [
        { xAxis: number; yAxis: number },
        { xAxis: number; yAxis: number },
      ] => item !== null,
    ) as Array<
    [{ xAxis: number; yAxis: number }, { xAxis: number; yAxis: number }]
  >;
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
        color: colors.value.aqua.darker,
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

const validatedLabels = computed(() => {
  if (!props.breakdownData?.validated_categories) return new Set<string>();
  return new Set(
    props.breakdownData.validated_categories
      .map((cat) => {
        const key = CATEGORY_LABEL_MAP[cat];
        return key ? t(key) : cat;
      }),
  );
});

const chartOption = computed((): EChartsOption => {
  const showUncertainties = props.viewUncertainties ?? false;

  // Build series array first (will be used to extract mapping)
  const seriesArray = [
    // Infrastructure — single emission type: energy
    {
      name: t('charts-energy-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: { x: 'category', y: 'energy' },
      markLine: {
        silent: true,
        symbol: ['none', 'none'],
        lineStyle: { color: '#333', width: 1.5, type: 'solid' as const },
        data: markLineData.value,
      },
      itemStyle: { color: colors.value.lilac.darker },
      label: { show: false },
    },
    // Equipment — subcategories: scientific, it, other
    {
      name: t('charts-scientific-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: { x: 'category', y: 'scientific' },
      itemStyle: { color: colors.value.mauve.darker },
      label: { show: false },
    },
    {
      name: t('charts-equipment-it'),
      type: 'bar' as const,
      stack: 'total',
      encode: { x: 'category', y: 'it' },
      itemStyle: { color: colors.value.mauve.dark },
      label: { show: false },
    },
    {
      name: t('charts-other-purchases-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: { x: 'category', y: 'other' },
      itemStyle: { color: colors.value.mauve.default },
      label: { show: false },
    },
    // Professional Travel — subcategories: plane, train
    {
      name: t('charts-plane-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: { x: 'category', y: 'plane' },
      itemStyle: { color: colors.value.babyBlue.darker },
      label: { show: false },
    },
    {
      name: t('charts-train-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: { x: 'category', y: 'train' },
      itemStyle: { color: colors.value.babyBlue.dark },
      label: { show: false },
    },
    // Research Core Facilities — emission types: stockage, virtualisation, calcul, ai_provider
    {
      name: t('charts-stockage-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: { x: 'category', y: 'stockage' },
      itemStyle: { color: colors.value.paleYellowGreen.darker },
      label: { show: false },
    },
    {
      name: t('charts-virtualisation-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: { x: 'category', y: 'virtualisation' },
      itemStyle: { color: colors.value.paleYellowGreen.dark },
      label: { show: false },
    },
    {
      name: t('charts-calcul-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: { x: 'category', y: 'calcul' },
      itemStyle: { color: colors.value.paleYellowGreen.default },
      label: { show: false },
    },
    {
      name: t('charts-ai-provider-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: { x: 'category', y: 'ai_provider' },
      itemStyle: { color: colors.value.paleYellowGreen.light },
      label: { show: false },
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
        const p = arr[0] as {
          data?: Record<string, unknown>;
          axisValue?: string;
          name?: string;
          seriesName?: string;
          marker?: string;
          value?: number | number[];
        };
        const data = p.data;
        const name = p.axisValue || p.name || '';
        let total = 0;
        let tooltip = `<strong>${name}</strong><br/>`;

        arr.reverse().forEach((param: unknown) => {
          const p = param as {
            seriesName?: string;
            marker?: string;
            value?: number | number[];
            data?: Record<string, unknown>;
          };
          // Find series by name to get its key
          const series = seriesArray.find((s) => s.name === p.seriesName);
          const key = series?.encode.y;

          const dataValue = Number(data[key]) || 0;
          if (dataValue > 0) {
            tooltip += `${p.marker || ''} ${series?.name || p.seriesName || ''}: <strong>${dataValue.toFixed(1)} </strong><br/>`;
            total += dataValue;
          }
        });

        let totalDisplay = total.toFixed(1);
        if (showUncertainties && data) {
          const stdDev = Math.sqrt(
            allStdDevKeys.value.reduce(
              (sum, k) => sum + Math.pow(Number(data[k]) || 0, 2),
              0,
            ),
          );
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
        formatter: (value: string) => {
          if (validatedLabels.value.has(value)) {
            return `{validated|${value}}`;
          }
          return `{unvalidated|${value}}`;
        },
        rich: {
          validated: {
            color: '#000000',
            fontSize: 11,
          },
          unvalidated: {
            color: '#aaaaaa',
            fontSize: 11,
          },
        },
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
          width: additionalDataConfig.value.scope2RectWidth,
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
        type: 'text',
        left: '56px',
        top: '30px',
        style: {
          fill: '#000000',
          text: t('charts-scope') + ' 2',
          font: '11px SuisseIntl',
        },
      },
      {
        type: 'rect',
        left: additionalDataConfig.value.scope3RectLeft,
        top: '15px',
        shape: {
          width: additionalDataConfig.value.scope3RectWidth,
          height: 300,
        },
        style: {
          fill: new graphic.LinearGradient(0, 0, 0, 1, [
            {
              offset: 0,
              color: 'rgba(229,229,229,0.9)',
            },
            {
              offset: 1,
              color: 'rgba(229,229,229,0.1)',
            },
          ]),
        },
      },
      {
        type: 'text',
        left: additionalDataConfig.value.scope3TextLeft,
        top: '30px',
        style: {
          fill: '#000000',
          text: t('charts-scope') + ' 3',
          font: '11px SuisseIntl',
        },
      },
      {
        type: 'text',
        left: '56px',
        top: '00px',
        style: {
          fill: '#000000',
          text: t('charts-main-category'),
          font: '11px SuisseIntl',
        },
      },
      ...(() => {
        if (toggleAdditionalData.value) {
          return [
            {
              type: 'text',
              left: additionalDataConfig.value.estimatedRectLeft + 10,
              top: '0px',
              style: {
                fill: '#000000',
                text: additionalDataConfig.value.estimatedText,
                font: '11px SuisseIntl',
              },
            },
            {
              type: 'rect',
              left: additionalDataConfig.value.estimatedRectLeft,
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
          ];
        }
        return [];
      })(),
    ],
    dataset: {
      dimensions: [
        'category',
        'energy', 'energyStdDev',
        'scientific', 'scientificStdDev',
        'it', 'itStdDev',
        'other', 'otherStdDev',
        'plane', 'planeStdDev',
        'train', 'trainStdDev',
        'stockage', 'stockageStdDev',
        'virtualisation', 'virtualisationStdDev',
        'calcul', 'calculStdDev',
        'ai_provider', 'ai_providerStdDev',
        'commuting', 'commutingStdDev',
        'food', 'foodStdDev',
        'waste', 'wasteStdDev',
        'greyEnergy', 'greyEnergyStdDev',
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
    link.download = `module-carbon-footprint-${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
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
  a.download = `module-carbon-footprint-${new Date().toISOString().replace(/[:.]/g, '-')}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
};
</script>

<template>
  <q-card flat class="container container--pa-none">
    <q-card-section class="flex justify-between items-center">
      <div>
        <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
          {{ $t('unit_carbon_footprint_title') }}
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
