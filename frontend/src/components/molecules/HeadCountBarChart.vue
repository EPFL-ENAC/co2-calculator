<script lang="ts" setup>
import { computed, nextTick, ref } from 'vue';
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
import TooltipEcharts from 'src/components/charts/results/TooltipEcharts.vue';
import { useEchartsTooltip } from 'src/components/charts/results/useEchartsTooltip';

import { colors } from 'src/constant/charts';
import { MODULES } from 'src/constant/modules';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
]);

const { t, te } = useI18n();
const chartRef = ref<InstanceType<typeof VChart>>();
const { tooltip, style, attach, emitTooltip } = useEchartsTooltip();

const onChartReady = async () => {
  await nextTick();
  const chart = chartRef.value?.chart;
  if (!chart) return;
  attach(chart);
};

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
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : params ? [params] : [];
        if (!arr.length) {
          emitTooltip(null);
          return '';
        }
        const p = arr[0] as {
          data?: { category: string; value: number };
          name?: string;
        };
        const val = p.data?.value ?? 0;
        const name = p.data?.category ?? p.name ?? '';
        if (val <= 0) {
          emitTooltip(null);
          return '';
        }
        emitTooltip({
          rows: [
            {
              label: name,
              value: `${Math.round(val * 10) / 10} ${t('module_total_result_title_unit', { type: MODULES.Headcount })}`,
              color: '#00a79f',
            },
          ],
        });
        return '';
      },
    },
    legend: { show: false },
    grid: { left: '3%', right: '4%', bottom: '50px', containLabel: true },
    dataset: {
      dimensions: ['category', 'value'],
      source: keys.map((key) => ({
        category: te(`headcount_${key}`) ? t(`headcount_${key}`) : key,
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
    <v-chart
      ref="chartRef"
      :option="chartOptions"
      autoresize
      @vue:mounted="onChartReady"
    />
    <Teleport to="body">
      <tooltip-echarts
        v-if="tooltip.visible"
        :tooltip-state="tooltip.data"
        :style="style"
      />
    </Teleport>
  </div>
</template>

<style lang="css" scoped>
.head-count-bar-chart {
  width: 100%;
  height: 400px;
}
</style>
