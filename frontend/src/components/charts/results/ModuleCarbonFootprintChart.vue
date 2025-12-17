<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import { graphic } from 'echarts';
import { getElement } from 'src/constant/charts';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';
import type { CallbackDataParams } from 'echarts/types/dist/shared';

interface AxisTooltipParams extends CallbackDataParams {
  axisValue: string;
  value: number;
  marker: string;
  seriesName: string;
}

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

const getDataArray = (baseData: number[]): number[] => {
  if (toggleAdditionalData.value) {
    return [...baseData, 0, 0, 0, 0];
  }
  return baseData;
};

const getUncertaintyDataArray = (baseData: number[]): number[] => {
  const showUncertainties = props.viewUncertainties ?? false;
  if (!showUncertainties) {
    // Return all zeros when uncertainty is disabled
    const length = toggleAdditionalData.value
      ? baseData.length + 4
      : baseData.length;
    return new Array(length).fill(0);
  }
  // Return actual uncertainty values when enabled
  return getDataArray(baseData);
};

const chartOption = computed((): EChartsOption => {
  // Explicitly reference props.viewUncertainties to ensure reactivity
  const showUncertainties = props.viewUncertainties ?? false;

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },

      formatter: function (params: AxisTooltipParams[]) {
        let total = 0;
        let tooltip = `<strong>${params[0].axisValue}</strong><br/>`;

        params.reverse().forEach((param: AxisTooltipParams) => {
          if (param.value > 0) {
            const isUncertainty = param.seriesName
              .toLowerCase()
              .includes('uncertainty');

            // Skip uncertainty series - we'll combine them with main series
            if (isUncertainty) {
              total += param.value;
              return;
            }

            // Find matching uncertainty series
            let displayValue = param.value.toString();
            if (showUncertainties) {
              const uncertaintyParam = params.find(
                (p) =>
                  p.seriesName.toLowerCase().includes('uncertainty') &&
                  p.seriesName.toLowerCase().replace(/\s+uncertainty$/, '') ===
                    param.seriesName.toLowerCase(),
              );
              if (uncertaintyParam && uncertaintyParam.value > 0) {
                displayValue = `${param.value} ± ${uncertaintyParam.value}`;
              }
            }

            tooltip += `${param.marker} ${param.seriesName}: <strong>${displayValue} </strong><br/>`;
            total += param.value;
          }
        });

        tooltip += `<hr style="margin: 4px 0"/>Total: <strong>${total.toFixed(1)}</strong>`;
        return tooltip;
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
      data: (() => {
        const baseCategories = [
          t('charts-unit-gas-category'),
          t('charts-infrastructure-gas-category'),
          t('charts-infrastructure-category'),
          t('charts-equipment-category'),
          t('charts-professional-travel-category'),
          t('charts-it-category'),
          t('charts-purchases-category'),
          t('charts-research-core-facilities-category'),
        ];
        if (toggleAdditionalData.value) {
          return [
            ...baseCategories,
            t('charts-commuting-category'),
            t('charts-food-category'),
            t('charts-waste-category'),
            t('charts-grey-energy-category'),
          ];
        }
        return baseCategories;
      })(),
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
    series: [
      {
        name: 'Unit Gas',
        type: 'bar',
        stack: 'total',
        data: getDataArray([2.5, 0, 0, 0, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('notDefined'),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Unit Gas Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0.5, 0, 0, 0, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('notDefined', 0, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Infrastructure Gas',
        type: 'bar',
        stack: 'total',
        data: getDataArray([0, 2, 0, 0, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('notDefined'),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Infrastructure Gas Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0.4, 0, 0, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('notDefined', 0, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Cooling',
        type: 'bar',
        stack: 'total',
        data: getDataArray([0, 0, 9, 0, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('blueGrey', 0),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Cooling Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 1.8, 0, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('blueGrey', 0, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Ventilation',
        type: 'bar',
        stack: 'total',
        data: getDataArray([0, 0, 3, 0, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('blueGrey', 1),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Ventilation Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 1, 0, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('blueGrey', 1, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Lighting',
        type: 'bar',
        stack: 'total',
        data: getDataArray([0, 0, 9, 0, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('blueGrey', 2),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Lighting Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 1.8, 0, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('blueGrey', 2, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Scientific',
        type: 'bar',
        stack: 'total',
        data: getDataArray([0, 0, 0, 10, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('purple', 0),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Scientific Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 2, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('purple', 0, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'IT',
        type: 'bar',
        stack: 'total',
        data: getDataArray([0, 0, 0, 3, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('purple', 1),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'IT Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0.6, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('purple', 1, 0.1),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Other',
        type: 'bar',
        stack: 'total',
        data: getDataArray([0, 0, 0, 0.2, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('purple', 2),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Other Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0.04, 0, 0, 0, 0]),
        itemStyle: {
          color: getElement('purple', 2, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Train',
        type: 'bar',
        stack: 'total',
        data: getDataArray([0, 0, 0, 0, 1.5, 0, 0, 0]),
        itemStyle: {
          color: getElement('blue', 0),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Train Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0, 0.3, 0, 0, 0]),
        itemStyle: {
          color: getElement('blue', 0, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Plane',
        type: 'bar',
        stack: 'total',
        data: getDataArray([0, 0, 0, 0, 3, 0, 0, 0]),
        itemStyle: {
          color: getElement('blue', 1),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'Plane Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0, 0.6, 0, 0, 0]),
        itemStyle: {
          color: getElement('blue', 1, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: 'IT Infrastructure',
        type: 'bar' as const,
        stack: 'total',
        data: getDataArray([0, 0, 0, 0, 0, 25, 0, 0]),
        itemStyle: {
          color: getElement('notDefined'),
        },
      },
      {
        name: 'IT Infrastructure Uncertainty',
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0, 0, 0.2, 0, 0]),
        itemStyle: {
          color: getElement('notDefined', 0, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-bio-chemicals-subcategory'),
        type: 'bar' as const,
        stack: 'total',
        data: getDataArray([0, 0, 0, 0, 0, 0, 2, 0]) as number[],
        itemStyle: {
          color: getElement('green', 0),
        },
      },
      {
        name: `${t('charts-bio-chemicals-subcategory')} Uncertainty`,
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0, 0, 0, 0.4, 0]) as number[],
        itemStyle: {
          color: getElement('green', 0, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-consumables-subcategory'),
        type: 'bar' as const,
        stack: 'total',
        data: getDataArray([0, 0, 0, 0, 0, 0, 3, 0]) as number[],
        itemStyle: {
          color: getElement('green', 1),
        },
      },
      {
        name: `${t('charts-consumables-subcategory')} Uncertainty`,
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0, 0, 0, 0.6, 0]) as number[],
        itemStyle: {
          color: getElement('green', 1, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-equipment-subcategory'),
        type: 'bar' as const,
        stack: 'total',
        data: getDataArray([0, 0, 0, 0, 0, 0, 1, 0]) as number[],
        itemStyle: {
          color: getElement('green', 2),
        },
      },
      {
        name: `${t('charts-equipment-subcategory')} Uncertainty`,
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0, 0, 0, 0.2, 0]) as number[],
        itemStyle: {
          color: getElement('green', 2, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-services-subcategory'),
        type: 'bar' as const,
        stack: 'total',
        data: getDataArray([0, 0, 0, 0, 0, 0, 2, 0]) as number[],
        itemStyle: {
          color: getElement('green', 3),
        },
      },
      {
        name: `${t('charts-services-subcategory')} Uncertainty`,
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0, 0, 0, 0.4, 0]) as number[],
        itemStyle: {
          color: getElement('green', 3, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-scitas-subcategory'),
        type: 'bar' as const,
        stack: 'total',
        data: getDataArray([0, 0, 0, 0, 0, 0, 0, 1]) as number[],
        itemStyle: {
          color: getElement('purpleGrey', 0),
        },
      },
      {
        name: `${t('charts-scitas-subcategory')} Uncertainty`,
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0, 0, 0, 0, 0.2]) as number[],
        itemStyle: {
          color: getElement('purpleGrey', 0, 0.5),
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-rcp-subcategory'),
        type: 'bar' as const,
        stack: 'total',
        data: getDataArray([0, 0, 0, 0, 0, 0, 0, 1.5]) as number[],
        itemStyle: {
          color: getElement('purpleGrey', 1),
        },
      },
      {
        name: `${t('charts-rcp-subcategory')} Uncertainty`,
        type: 'bar' as const,
        stack: 'total',
        data: getUncertaintyDataArray([0, 0, 0, 0, 0, 0, 0, 0.3]) as number[],
        itemStyle: {
          color: getElement('purpleGrey', 1, 0.5),
        },
        label: {
          show: false,
        },
      },

      ...(() => {
        if (toggleAdditionalData.value) {
          const getAdditionalUncertaintyData = (
            baseData: number[],
          ): number[] => {
            const showUncertainties = props.viewUncertainties ?? false;
            if (!showUncertainties) {
              return new Array(12).fill(0);
            }
            return baseData;
          };

          return [
            {
              name: 'Commuting',
              type: 'bar' as const,
              stack: 'total',
              data: [0, 0, 0, 0, 0, 0, 0, 0, 8, 0, 0, 0] as number[],
              itemStyle: {
                color: getElement('tealBlue'),
              },
            },
            {
              name: 'Commuting Uncertainty',
              type: 'bar' as const,
              stack: 'total',
              data: getAdditionalUncertaintyData([
                0, 0, 0, 0, 0, 0, 0, 0, 1.6, 0, 0, 0,
              ]) as number[],
              itemStyle: {
                color: getElement('tealBlue', 0, 0.5),
              },
              label: {
                show: false,
              },
            },
            {
              name: 'Food',
              type: 'bar' as const,
              stack: 'total',
              data: [0, 0, 0, 0, 0, 0, 0, 0, 0, 2.5, 0, 0] as number[],
              itemStyle: {
                color: getElement('forestGreen'),
              },
            },
            {
              name: 'Food Uncertainty',
              type: 'bar' as const,
              stack: 'total',
              data: getAdditionalUncertaintyData([
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0.5, 0, 0,
              ]) as number[],
              itemStyle: {
                color: getElement('forestGreen', 0, 0.5),
              },
              label: {
                show: false,
              },
            },
            {
              name: t('charts-waste-category'),
              type: 'bar' as const,
              stack: 'total',
              data: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 0] as number[],
              itemStyle: {
                color: getElement('limeGreen'),
              },
            },
            {
              name: `${t('charts-waste-category')} Uncertainty`,
              type: 'bar' as const,
              stack: 'total',
              data: getAdditionalUncertaintyData([
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0,
              ]) as number[],
              itemStyle: {
                color: getElement('limeGreen', 0, 0.5),
              },
              label: {
                show: false,
              },
            },
            {
              name: t('charts-grey-energy-category'),
              type: 'bar' as const,
              stack: 'total',
              data: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4] as number[],
              itemStyle: {
                color: getElement('neutralGrey'),
              },
            },
            {
              name: `${t('charts-grey-energy-category')} Uncertainty`,
              type: 'bar' as const,
              stack: 'total',
              data: getAdditionalUncertaintyData([
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.8,
              ]) as number[],
              itemStyle: {
                color: getElement('neutralGrey', 0, 0.5),
              },
              label: {
                show: false,
              },
            },
          ];
        }
        return [];
      })(),
    ],
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
