<script setup lang="ts">
import { ref, onMounted } from 'vue';
import * as echarts from 'echarts';
import type { EChartsOption, BarSeriesOption } from 'echarts';
import { getElementColor } from 'src/constant/chart-colors';

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

// Category colors using the chart color scale utility
const categoryColors: Record<string, string> = {
  'Unit-gas': getElementColor('unit-gas'),
  'Infrastructure-gas': getElementColor('infrastructure-gas'),
  Infrastructure: getElementColor('infrastructure-category'),
  Equipment: getElementColor('equipment'),
  Commuting: getElementColor('commuting'),
  Food: getElementColor('food'),
  'Professional Travel': getElementColor('professional-travel-category'),
  IT: getElementColor('it'),
  'Research Core Facilities': getElementColor('research-core-facilities'),
  Purchases: getElementColor('purchases'),
  Waste: getElementColor('waste'),
  'Grey Energy': getElementColor('grey-energy'),
};

// Data structure based on the image description
const categories = [
  'Unit-gas',
  'Infrastructure-gas',
  'Infrastructure',
  'Equipment',
  'Commuting',
  'Food',
  'Professional Travel',
  'IT',
  'Research Core Facilities',
  'Purchases',
  'Waste',
  'Grey Energy',
];

// Series data based on the image description
const seriesData: BarSeriesOption[] = categories.map((category) => {
  const values: (number | null)[] = [];

  // Scope 1 - Bar 1
  if (category === 'Unit-gas') values.push(2.5);
  else if (category === 'Infrastructure-gas') values.push(1.0);
  else values.push(null);

  // Scope 1 - Bar 2
  if (category === 'Professional Travel') values.push(3.0);
  else if (category === 'Infrastructure-gas') values.push(2.0);
  else values.push(null);

  // Scope 2 - Bar 1
  if (category === 'Purchases') values.push(9.0);
  else if (category === 'Equipment') values.push(3.0);
  else values.push(null);

  // Scope 2 - Bar 2
  if (category === 'Research Core Facilities') values.push(10.0);
  else if (category === 'IT') values.push(3.0);
  else values.push(null);

  // Scope 3 - Bar 1
  if (category === 'Food') values.push(8.0);
  else if (category === 'Commuting') values.push(8.0);
  else values.push(null);

  // Scope 3 - Bar 2
  if (category === 'Equipment') values.push(2.5);
  else if (category === 'IT') values.push(3.0);
  else values.push(null);

  // Scope 3 - Bar 3
  if (category === 'Infrastructure') values.push(1.5);
  else if (category === 'Research Core Facilities') values.push(3.0);
  else values.push(null);

  // Scope 3 - Bar 4
  if (category === 'Professional Travel') values.push(25.0);
  else if (category === 'Commuting') values.push(8.0);
  else values.push(null);

  // Scope 3 - Bar 5
  if (category === 'Purchases') values.push(3.0);
  else values.push(null);

  // Scope 3 - Bar 6
  if (category === 'Waste') values.push(2.0);
  else if (category === 'Grey Energy') values.push(3.0);
  else values.push(null);

  // Estimated - Bar 1
  if (category === 'Purchases') values.push(9.0);
  else if (category === 'Waste') values.push(3.0);
  else values.push(null);

  // Estimated - Bar 2
  if (category === 'Waste') values.push(10.0);
  else if (category === 'Grey Energy') values.push(4.0);
  else values.push(null);

  // Estimated - Bar 3
  if (category === 'Purchases') values.push(6.0);
  else values.push(null);

  // Estimated - Bar 4
  if (category === 'Grey Energy') values.push(4.0);
  else values.push(null);

  return {
    name: category,
    type: 'bar',
    stack: 'total',
    data: values,
    barWidth: '70%',
    barCategoryGap: '20%',
    itemStyle: {
      color: categoryColors[category],
    },
  } as BarSeriesOption;
});

const initChart = () => {
  if (!chartRef.value) return;

  chartInstance = echarts.init(chartRef.value);

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      formatter: (params: unknown) => {
        if (Array.isArray(params) && params.length > 0) {
          const firstParam = params[0] as {
            axisValue?: string;
            marker?: string;
            seriesName?: string;
            value?: number | null;
          };
          if (!firstParam) {
            return '';
          }
          const axisValue = firstParam.axisValue || '';
          let result = `${axisValue}<br/>`;
          let total = 0;
          params.forEach((param) => {
            const p = param as {
              marker?: string;
              seriesName?: string;
              value?: number | null;
            };
            if (
              p &&
              p.value !== null &&
              p.value !== undefined &&
              typeof p.value === 'number'
            ) {
              result += `${p.marker || ''}${p.seriesName || ''}: ${p.value.toFixed(1)} t CO₂-eq<br/>`;
              total += p.value;
            }
          });
          result += `<b>Total: ${total.toFixed(1)} t CO₂-eq</b>`;
          return result;
        }
        return '';
      },
    },
    legend: {
      data: categories,
      bottom: 0,
      type: 'plain',
      orient: 'horizontal',
      itemGap: 8,
      itemWidth: 10,
      itemHeight: 10,
    },
    grid: {
      left: '10%',
      right: '4%',
      bottom: '15%',
      top: '0%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',

      axisLabel: {
        show: false,
      },
      boundaryGap: true,
    },
    yAxis: {
      type: 'value',
      name: 't CO₂-eq',
      nameLocation: 'middle',
      nameGap: 50,
      nameRotate: 90,
      nameTextStyle: {
        fontSize: 10,
        fontWeight: 'normal',
      },
      max: 35,
      splitLine: {
        show: true,
        lineStyle: {
          color: '#E0E0E0',
          type: 'solid',
        },
      },
    },
    series: [
      // Background areas for scopes (progressively greyer)
      {
        type: 'bar',
        data: [],
        markArea: {
          silent: true,
          itemStyle: {
            color: '#F5F5F5', // Light grey for Scope 1
            opacity: 0.3,
          },
          label: {
            show: true,
            position: [0.5, 0], // Center of xAxis 0-1, at top
            formatter: 'Scope 1',
            fontSize: 12,
            fontWeight: 'bold',
            color: '#333',
          },
          data: [
            [{ xAxis: 0 }, { xAxis: 1 }], // Scope 1 (bars 0-1)
          ],
        },
        z: 0,
      } as BarSeriesOption,
      {
        type: 'bar',
        data: [],
        markArea: {
          silent: true,
          itemStyle: {
            color: '#E8E8E8', // Medium grey for Scope 2
            opacity: 0.3,
          },
          label: {
            show: true,
            position: [2.5, 0], // Center of xAxis 2-3, at top
            formatter: 'Scope 2',
            fontSize: 12,
            fontWeight: 'bold',
            color: '#333',
          },
          data: [
            [{ xAxis: 2 }, { xAxis: 3 }], // Scope 2 (bars 2-3)
          ],
        },
        z: 0,
      } as BarSeriesOption,
      {
        type: 'bar',
        data: [],
        markArea: {
          silent: true,
          itemStyle: {
            color: '#D0D0D0', // Darker grey for Scope 3
            opacity: 0.3,
          },
          label: {
            show: true,
            position: [6.5, 0], // Center of xAxis 4-9, at top
            formatter: 'Scope 3',
            fontSize: 12,
            fontWeight: 'bold',
            color: '#333',
          },
          data: [
            [{ xAxis: 4 }, { xAxis: 9 }], // Scope 3 (bars 4-9)
          ],
        },
        z: 0,
      } as BarSeriesOption,
      {
        type: 'bar',
        data: [],
        markArea: {
          silent: true,
          itemStyle: {
            color: '#D0D0D0', // Darkest grey for Estimated (darker than Scope 3)
            opacity: 0.3,
          },
          label: {
            show: true,
            position: [11.5, 0], // Center of xAxis 10-13, at top
            formatter: 'Estimated',
            fontSize: 12,
            fontWeight: 'bold',
            color: '#333',
          },
          data: [
            [{ xAxis: 10 }, { xAxis: 13 }], // Estimated (bars 10-13)
          ],
        },
        z: 0,
      } as BarSeriesOption,
      // Dotted line separator between Scope 3 and Estimated
      {
        type: 'bar',
        data: [],
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            color: '#666',
            type: 'dashed',
            width: 2,
          },
          data: [
            [
              {
                xAxis: 10, // Between bar 9 (last Scope 3) and bar 10 (first Estimated)
                yAxis: 0,
              },
              {
                xAxis: 10,
                yAxis: 35, // Full height
              },
            ],
          ],
        },
        z: 10,
      } as BarSeriesOption,

      ...seriesData,
    ],
  };

  chartInstance.setOption(option);

  // Handle window resize
  const handleResize = () => {
    chartInstance?.resize();
  };
  window.addEventListener('resize', handleResize);
};

onMounted(() => {
  initChart();
});
</script>

<template>
  <div
    ref="chartRef"
    style="width: 100%; height: 500px; min-height: 500px"
  ></div>
</template>
