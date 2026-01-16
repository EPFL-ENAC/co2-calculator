<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

const { t } = useI18n();

use([
  CanvasRenderer,
  LineChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
]);

const props = defineProps<{
  colorScheme: {
    darker: string;
    dark: string;
    default: string;
    light: string;
    lighter: string;
  };
}>();

const moduleStore = useModuleStore();
const workspaceStore = useWorkspaceStore();

// Fetch evolution over time data when unit changes
watch(
  () => workspaceStore.selectedUnit?.id,
  (unitId) => {
    if (unitId) {
      moduleStore.getTravelEvolutionOverTime(unitId);
    }
  },
  { immediate: true },
);

onMounted(() => {
  const unitId = workspaceStore.selectedUnit?.id;
  if (unitId) {
    moduleStore.getTravelEvolutionOverTime(unitId);
  }
});

// Process real data from API
const chartData = computed(() => {
  const rawData = moduleStore.state.travelEvolutionOverTime as Array<{
    year: number;
    transport_mode: string;
    kg_co2eq: number;
  }>;

  if (!rawData || rawData.length === 0) {
    return {
      years: [],
      plane: [],
      train: [],
    };
  }

  // Get unique years and sort them
  const yearsSet = new Set<number>();
  rawData.forEach((item) => {
    if (item.year) {
      yearsSet.add(item.year);
    }
  });
  const years = Array.from(yearsSet).sort((a, b) => a - b);

  // Group data by transport mode and year
  const dataByMode: Record<string, Record<number, number>> = {
    flight: {},
    train: {},
  };

  rawData.forEach((item) => {
    const mode = item.transport_mode === 'flight' ? 'flight' : 'train';
    const year = item.year;
    const value = item.kg_co2eq || 0;

    if (!dataByMode[mode][year]) {
      dataByMode[mode][year] = 0;
    }
    dataByMode[mode][year] += value;
  });

  // Build arrays for each year
  const plane: number[] = [];
  const train: number[] = [];

  years.forEach((year) => {
    plane.push(dataByMode.flight[year] || 0);
    train.push(dataByMode.train[year] || 0);
  });

  return {
    years,
    plane,
    train,
  };
});

const chartOption = computed((): EChartsOption => {
  return {
    backgroundColor: 'transparent',
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true,
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = params as Array<{
          seriesName?: string;
          value?: number;
          color?: string;
        }>;
        let tooltip = `<strong>${p[0]?.seriesName || ''}</strong><br/>`;
        p.forEach((item) => {
          tooltip += `<span style="display:inline-block;margin-right:5px;border-radius:10px;width:10px;height:10px;background-color:${item.color};"></span>`;
          tooltip += `${item.seriesName}: <strong>${item.value?.toFixed(0)}</strong><br/>`;
        });
        return tooltip;
      },
    },
    legend: {
      data: [t('plane', 'plane'), t('train', 'train')],
      top: 0,
      left: 'center',
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: chartData.value.years.map((y) => String(y)),
      axisLabel: {
        formatter: (value: string) => value,
      },
    },
    yAxis: {
      type: 'value',
      name: 'kg CO₂eq',
      nameLocation: 'middle',
      nameGap: 50,
      axisLabel: {
        formatter: (value: number) => {
          if (value >= 1000) {
            return `${(value / 1000).toFixed(0)}k`;
          }
          return String(value);
        },
      },
    },
    series: [
      {
        name: t('plane', 'plane'),
        type: 'line',
        data: chartData.value.plane,
        smooth: true,
        lineStyle: {
          color: props.colorScheme.darker,
          width: 3,
        },
        itemStyle: {
          color: props.colorScheme.darker,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              {
                offset: 0,
                color: props.colorScheme.darker,
              },
              {
                offset: 1,
                color: props.colorScheme.lighter,
              },
            ],
          },
          opacity: 0.3,
        },
      },
      {
        name: t('train', 'train'),
        type: 'line',
        data: chartData.value.train,
        smooth: true,
        lineStyle: {
          color: props.colorScheme.dark,
          width: 3,
        },
        itemStyle: {
          color: props.colorScheme.dark,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              {
                offset: 0,
                color: props.colorScheme.dark,
              },
              {
                offset: 1,
                color: props.colorScheme.lighter,
              },
            ],
          },
          opacity: 0.3,
        },
      },
    ],
  };
});

const chartRef = ref<InstanceType<typeof VChart>>();
</script>

<template>
  <q-card-section class="chart-container q-pa-none">
    <div
      v-if="moduleStore.state.loadingTravelEvolutionOverTime"
      class="text-body2 text-secondary"
    >
      Loading chart data...
    </div>
    <div
      v-else-if="moduleStore.state.errorTravelEvolutionOverTime"
      class="text-body2 text-error"
    >
      Error loading data: {{ moduleStore.state.errorTravelEvolutionOverTime }}
    </div>
    <div
      v-else-if="chartData.years.length === 0"
      class="text-body2 text-secondary"
    >
      No data available
    </div>
    <v-chart
      v-else
      ref="chartRef"
      class="chart"
      autoresize
      :option="chartOption"
    />
  </q-card-section>
</template>

<style scoped>
.chart {
  width: 100%;
  height: 400px;
}

.chart-container {
  padding: 0 !important;
  margin: 0 !important;
}

.chart :deep(canvas) {
  display: block;
}
</style>
