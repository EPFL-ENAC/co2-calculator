<script lang="ts" setup>
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
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
const chartOptions: EChartsOption = {
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'shadow',
    },
  },
  legend: {
    bottom: 10,
    left: 10,
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '50px',
    containLabel: true,
  },
  yAxis: {
    type: 'value',
    boundaryGap: [0, 0.01],
  },
  xAxis: {
    type: 'category',
    data: ['Team Leader', 'RSE', 'Student'],
  },
  series: [
    {
      name: 'EPT',
      type: 'bar',
      data: [1, 1, 4],
      itemStyle: {
        color: '#00a79f',
        // color: new graphic.LinearGradient(0, 0, 1, 0, [
        //   { offset: 0, color: colors.value.oliveGreen.dark },
        //   { offset: 1, color: colors.value.oliveGreen.light },
        // ]),
      },
    },
  ],
};
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
