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

const additionalDataConfig = computed(() => {
  if (toggleAdditionalData.value) {
    return {
      firstRectWidth: 72,
      secondRectLeft: 118,
      secondRectWidth: 75,
      secondTextLeft: 128,
      thirdRectLeft: 193,
      thirdRectWidth: 500,
      thirdTextLeft: 203,
      estimatedText: t('charts-additional-category'),
    };
  }

  return {
    firstRectWidth: 109,
    secondRectLeft: 155,
    secondRectWidth: 108,
    secondTextLeft: 165,
    thirdRectLeft: 263,
    thirdRectWidth: 500,
    thirdTextLeft: 273,
    estimatedText: '',
  };
});

const markLineData = computed(() => {
  const showUncertainties = props.viewUncertainties ?? false;
  if (!showUncertainties) return [];

  const datasetSource = (() => {
    const baseData = [
      {
        category: t('charts-unit-gas-category'),
        unitGas: 2.5,
        unitGasStdDev: 0.5,
      },
      {
        category: t('charts-infrastructure-gas-category'),
        infrastructureGas: 2,
        infrastructureGasStdDev: 0.5,
      },
      {
        category: t('charts-infrastructure-category'),
        cooling: 9,
        coolingStdDev: 1.8,
        ventilation: 3,
        ventilationStdDev: 1,
        lighting: 9,
        lightingStdDev: 1.8,
      },
      {
        category: t('charts-equipment-category'),
        scientific: 10,
        scientificStdDev: 2,
        it: 3,
        itStdDev: 0.6,
        other: 0.2,
        otherStdDev: 0.04,
      },
      {
        category: t('charts-professional-travel-category'),
        train: 1.5,
        trainStdDev: 0.3,
        plane: 3,
        planeStdDev: 0.6,
      },
      {
        category: t('charts-it-category'),
        itInfrastructure: 25,
        itInfrastructureStdDev: 0.2,
      },
      {
        category: t('charts-purchases-category'),
        bioChemicals: 2,
        bioChemicalsStdDev: 0.4,
        consumables: 3,
        consumablesStdDev: 0.6,
        equipment: 1,
        equipmentStdDev: 0.2,
        services: 2,
        servicesStdDev: 0.4,
      },
      {
        category: t('charts-research-core-facilities-category'),
        scitas: 1,
        scitasStdDev: 0.2,
        rcp: 1.5,
        rcpStdDev: 0.3,
      },
    ];

    if (toggleAdditionalData.value) {
      return [
        ...baseData,
        {
          category: t('charts-commuting-category'),
          commuting: 8,
          commutingStdDev: 1.6,
        },
        {
          category: t('charts-food-category'),
          food: 2.5,
          foodStdDev: 0.5,
        },
        {
          category: t('charts-waste-category'),
          waste: 10,
          wasteStdDev: 2,
        },
        {
          category: t('charts-grey-energy-category'),
          greyEnergy: 4,
          greyEnergyStdDev: 2,
        },
      ];
    }
    return baseData;
  })();

  const allValueKeys = [
    'unitGas',
    'infrastructureGas',
    'cooling',
    'ventilation',
    'lighting',
    'scientific',
    'it',
    'other',
    'train',
    'plane',
    'itInfrastructure',
    'bioChemicals',
    'consumables',
    'equipment',
    'services',
    'scitas',
    'rcp',
  ];

  const allStdDevKeys = [
    'unitGasStdDev',
    'infrastructureGasStdDev',
    'coolingStdDev',
    'ventilationStdDev',
    'lightingStdDev',
    'scientificStdDev',
    'itStdDev',
    'otherStdDev',
    'trainStdDev',
    'planeStdDev',
    'itInfrastructureStdDev',
    'bioChemicalsStdDev',
    'consumablesStdDev',
    'equipmentStdDev',
    'servicesStdDev',
    'scitasStdDev',
    'rcpStdDev',
  ];

  if (toggleAdditionalData.value) {
    allValueKeys.push('commuting', 'food', 'waste', 'greyEnergy');
    allStdDevKeys.push(
      'commutingStdDev',
      'foodStdDev',
      'wasteStdDev',
      'greyEnergyStdDev',
    );
  }

  return datasetSource
    .map((item, i) => {
      const total = allValueKeys.reduce((sum, k) => sum + (item[k] || 0), 0);
      if (total <= 0) return null;
      const stdDev = Math.sqrt(
        allStdDevKeys.reduce((sum, k) => sum + Math.pow(item[k] || 0, 2), 0),
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
        color: colors.value.tealBlue.default,
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
        color: colors.value.forestGreen.default,
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
        color: colors.value.limeGreen.default,
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
        color: colors.value.neutralGrey.default,
      },
    },
  ];
});

const chartOption = computed((): EChartsOption => {
  const showUncertainties = props.viewUncertainties ?? false;

  const datasetSource = (() => {
    const baseData = [
      {
        category: t('charts-unit-gas-category'),
        unitGas: 2.5,
        unitGasStdDev: 0.5,
      },
      {
        category: t('charts-infrastructure-gas-category'),
        infrastructureGas: 2,
        infrastructureGasStdDev: 0.5,
      },
      {
        category: t('charts-infrastructure-category'),
        cooling: 9,
        coolingStdDev: 1.8,
        ventilation: 3,
        ventilationStdDev: 1,
        lighting: 9,
        lightingStdDev: 1.8,
      },
      {
        category: t('charts-equipment-category'),
        scientific: 10,
        scientificStdDev: 2,
        it: 3,
        itStdDev: 0.6,
        other: 0.2,
        otherStdDev: 0.04,
      },
      {
        category: t('charts-professional-travel-category'),
        train: 1.5,
        trainStdDev: 0.3,
        plane: 3,
        planeStdDev: 0.6,
      },
      {
        category: t('charts-it-category'),
        itInfrastructure: 25,
        itInfrastructureStdDev: 0.2,
      },
      {
        category: t('charts-purchases-category'),
        bioChemicals: 2,
        bioChemicalsStdDev: 0.4,
        consumables: 3,
        consumablesStdDev: 0.6,
        equipment: 1,
        equipmentStdDev: 0.2,
        services: 2,
        servicesStdDev: 0.4,
      },
      {
        category: t('charts-research-core-facilities-category'),
        scitas: 1,
        scitasStdDev: 0.2,
        rcp: 1.5,
        rcpStdDev: 0.3,
      },
    ];

    if (toggleAdditionalData.value) {
      return [
        ...baseData,
        {
          category: t('charts-commuting-category'),
          commuting: 8,
          commutingStdDev: 1.6,
        },
        {
          category: t('charts-food-category'),
          food: 2.5,
          foodStdDev: 0.5,
        },
        {
          category: t('charts-waste-category'),
          waste: 10,
          wasteStdDev: 2,
        },
        {
          category: t('charts-grey-energy-category'),
          greyEnergy: 4,
          greyEnergyStdDev: 2,
        },
      ];
    }
    return baseData;
  })();

  // Define series order for total error bar calculation
  const allValueKeys = [
    'unitGas',
    'infrastructureGas',
    'cooling',
    'ventilation',
    'lighting',
    'scientific',
    'it',
    'other',
    'train',
    'plane',
    'itInfrastructure',
    'bioChemicals',
    'consumables',
    'equipment',
    'services',
    'scitas',
    'rcp',
  ];

  const allStdDevKeys = [
    'unitGasStdDev',
    'infrastructureGasStdDev',
    'coolingStdDev',
    'ventilationStdDev',
    'lightingStdDev',
    'scientificStdDev',
    'itStdDev',
    'otherStdDev',
    'trainStdDev',
    'planeStdDev',
    'itInfrastructureStdDev',
    'bioChemicalsStdDev',
    'consumablesStdDev',
    'equipmentStdDev',
    'servicesStdDev',
    'scitasStdDev',
    'rcpStdDev',
  ];

  if (toggleAdditionalData.value) {
    allValueKeys.push('commuting', 'food', 'waste', 'greyEnergy');
    allStdDevKeys.push(
      'commutingStdDev',
      'foodStdDev',
      'wasteStdDev',
      'greyEnergyStdDev',
    );
  }

  // Build series array first (will be used to extract mapping)
  const seriesArray = [
    {
      name: t('charts-unit-gas-category'),
      type: 'bar',
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
        color: colors.value.notDefined.default,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-infrastructure-gas-category'),
      type: 'bar',
      stack: 'total',
      encode: {
        x: 'category',
        y: 'infrastructureGas',
      },
      itemStyle: {
        color: colors.value.notDefined.default,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-cooling-subcategory'),
      type: 'bar',
      stack: 'total',
      encode: {
        x: 'category',
        y: 'cooling',
      },
      itemStyle: {
        color: colors.value.blueGrey.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-ventilation-subcategory'),
      type: 'bar',
      stack: 'total',
      encode: {
        x: 'category',
        y: 'ventilation',
      },
      itemStyle: {
        color: colors.value.blueGrey.dark,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-lighting-subcategory'),
      type: 'bar',
      stack: 'total',
      encode: {
        x: 'category',
        y: 'lighting',
      },
      itemStyle: {
        color: colors.value.blueGrey.default,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-scientific-subcategory'),
      type: 'bar',
      stack: 'total',
      encode: {
        x: 'category',
        y: 'scientific',
      },
      itemStyle: {
        color: colors.value.purple.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-it-subcategory'),
      type: 'bar',
      stack: 'total',
      encode: {
        x: 'category',
        y: 'it',
      },
      itemStyle: {
        color: colors.value.purple.dark,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-other-purchases-subcategory'),
      type: 'bar',
      stack: 'total',
      encode: {
        x: 'category',
        y: 'other',
      },
      itemStyle: {
        color: colors.value.purple.default,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-train-subcategory'),
      type: 'bar',
      stack: 'total',
      encode: {
        x: 'category',
        y: 'train',
      },
      itemStyle: {
        color: colors.value.blue.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-plane-subcategory'),
      type: 'bar',
      stack: 'total',
      encode: {
        x: 'category',
        y: 'plane',
      },
      itemStyle: {
        color: colors.value.blue.dark,
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
        color: colors.value.notDefined.default,
      },
    },
    {
      name: t('charts-bio-chemicals-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'bioChemicals',
      },
      itemStyle: {
        color: colors.value.green.darker,
      },
    },
    {
      name: t('charts-consumables-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'consumables',
      },
      itemStyle: {
        color: colors.value.green.dark,
      },
    },
    {
      name: t('charts-equipment-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'equipment',
      },
      itemStyle: {
        color: colors.value.green.default,
      },
    },
    {
      name: t('charts-services-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'services',
      },
      itemStyle: {
        color: colors.value.green.light,
      },
    },
    {
      name: t('charts-scitas-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'scitas',
      },
      itemStyle: {
        color: colors.value.purpleGrey.darker,
      },
    },
    {
      name: t('charts-rcp-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      encode: {
        x: 'category',
        y: 'rcp',
      },
      itemStyle: {
        color: colors.value.purpleGrey.dark,
      },
    },
    ...additionalSeriesData.value,
  ];

  const seriesNameToKey = Object.fromEntries(
    seriesArray.map((s) => [s.name, s.encode.y]),
  ) as Record<string, string>;

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
          const key = seriesNameToKey[p.seriesName || ''];
          const val =
            (data && key
              ? Number(data[key])
              : Array.isArray(p.value)
                ? p.value[1]
                : p.value) || 0;
          if (val > 0) {
            tooltip += `${p.marker || ''} ${p.seriesName}: <strong>${val.toFixed(1)} </strong><br/>`;
            total += val;
          }
        });

        let totalDisplay = total.toFixed(1);
        if (showUncertainties && data) {
          const stdDev = Math.sqrt(
            allStdDevKeys.reduce(
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
      top: '3%',
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
      max: 30,
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
          width: additionalDataConfig.value.firstRectWidth,
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
        left: '56px', // Position at horizontal center according to its parent.
        top: '30px', // Position at vertical center according to its parent.
        style: {
          fill: '#000000',
          text: t('charts-scope') + ' 1',
          font: '11px SuisseIntl',
        },
      },
      {
        type: 'rect',
        left: additionalDataConfig.value.secondRectLeft,
        top: '15px',
        shape: {
          width: additionalDataConfig.value.secondRectWidth,
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
        left: additionalDataConfig.value.secondTextLeft,
        top: '30px', // Position at vertical center according to its parent.
        style: {
          fill: '#000000',
          text: t('charts-scope') + ' 2',
          font: '11px SuisseIntl',
        },
      },
      {
        type: 'rect',
        left: additionalDataConfig.value.thirdRectLeft,
        top: '15px',
        shape: {
          width: additionalDataConfig.value.thirdRectWidth,
          height: 300,
        },
        style: {
          fill: new graphic.LinearGradient(0, 0, 0, 1, [
            {
              offset: 0,
              color: 'rgba(210,210,210,0.9)',
            },
            {
              offset: 1,
              color: 'rgba(210,210,210,0.1)',
            },
          ]),
        },
      },
      {
        type: 'text',
        left: additionalDataConfig.value.thirdTextLeft,
        top: '30px', // Position at vertical center according to its parent.
        style: {
          fill: '#000000',
          text: t('charts-scope') + ' 3',
          font: '11px SuisseIntl',
        },
      },
      {
        type: 'text',
        left: '56px', // Position at horizontal center according to its parent.
        top: '00px', // Position at vertical center according to its parent.
        style: {
          fill: '#000000',
          text: t('charts-main-category'),
          font: '11px SuisseIntl',
        },
      },
      {
        type: 'text',
        left: '345px',
        top: '0px', // Position at vertical center according to its parent.
        style: {
          fill: '#000000',
          text: additionalDataConfig.value.estimatedText,
          font: '11px SuisseIntl',
        },
      },
      ...(() => {
        if (toggleAdditionalData.value) {
          return [
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
          ];
        }
        return [];
      })(),
    ],
    dataset: {
      dimensions: [
        'category',
        'unitGas',
        'unitGasStdDev',
        'infrastructureGas',
        'infrastructureGasStdDev',
        'cooling',
        'coolingStdDev',
        'ventilation',
        'ventilationStdDev',
        'lighting',
        'lightingStdDev',
        'scientific',
        'scientificStdDev',
        'it',
        'itStdDev',
        'other',
        'otherStdDev',
        'train',
        'trainStdDev',
        'plane',
        'planeStdDev',
        'itInfrastructure',
        'itInfrastructureStdDev',
        'bioChemicals',
        'bioChemicalsStdDev',
        'consumables',
        'consumablesStdDev',
        'equipment',
        'equipmentStdDev',
        'services',
        'servicesStdDev',
        'scitas',
        'scitasStdDev',
        'rcp',
        'rcpStdDev',
        'commuting',
        'commutingStdDev',
        'food',
        'foodStdDev',
        'waste',
        'wasteStdDev',
        'greyEnergy',
        'greyEnergyStdDev',
      ],
      source: datasetSource as Array<Record<string, unknown>>,
    },
    series: seriesArray as echarts.SeriesOption[],
  };
});
</script>

<template>
  <q-card flat class="container container--pa-none">
    <q-card-section class="flex justify-between items-center">
      <div>
        <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
          {{ $t('unit_carbon_footprint_title') }}
        </span>
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
