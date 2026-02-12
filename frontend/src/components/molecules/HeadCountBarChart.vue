<script lang="ts" setup>
import { computed } from 'vue';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import { useI18n } from 'vue-i18n';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';

import { colors } from 'src/constant/charts';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
]);

const { t } = useI18n();

const props = withDefaults(
  defineProps<{
    stats?: Record<string, number>;
  }>(),
  {
    stats: () => ({}),
  },
);
const OVERRIDE = false;
// Define colors for each key
const colorMap: Record<string, string> = {
  professor: colors.value.mint.dark,
  scientific_collaborator: colors.value.mint.light,
  postdoctoral_researcher: colors.value.mint.darker,
  doctoral_assistant: colors.value.mint.default,
  trainee: colors.value.mint.lighter,
  student: colors.value.mint.default,
  technical_administrative_staff: colors.value.mint.light,
  other: colors.value.mint.darker,
};

const chartOptions = computed<EChartsOption>(() => {
  const keys = Object.keys(props.stats ?? {});

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: { show: false },
    grid: { left: '3%', right: '4%', bottom: '50px', containLabel: true },
    dataset: {
      dimensions: ['category', 'value'],
      source: keys.map((key) => ({
        category: t(`app_headcount_${key}`),
        value: Math.round((props.stats?.[key] ?? 0) * 10) / 10,
      })),
    },
    xAxis: {
      type: 'category',
      axisLabel: {
        interval: 0, // Force showing all labels
        rotate: 45, // Rotate labels if needed
        fontSize: 12,
      },
    },
    yAxis: { type: 'value', boundaryGap: [0, 0.01] },
    series: [
      {
        type: 'bar',
        encode: { x: 'category', y: 'value' },
        itemStyle: {
          color: (params) => {
            // const key = keys[params.dataIndex];
            // return colorMap[key] || '#00a79f';
            if (OVERRIDE) {
              const key = keys[params.dataIndex];
              return colorMap[key] || '#00a79f';
            }
            return '#00a79f';
          },
        },
      },
    ],
  };
});
</script>

<template>
  <div class="head-count-bar-chart">
    <v-chart :option="chartOptions" autoresize />
  </div>
</template>

<style lang="css" scoped>
.head-count-bar-chart {
  width: 100%;
  height: 400px;
}
</style>
