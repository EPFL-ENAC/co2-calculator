<script setup lang="ts">
import { computed, ref } from 'vue';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { TreemapChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import {
  TooltipComponent,
  LegendComponent,
  DatasetComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';

use([
  CanvasRenderer,
  TreemapChart,
  TooltipComponent,
  LegendComponent,
  DatasetComponent,
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

const datasetSource = computed(() => {
  return [
    {
      category: 'plane',
      business: 6,
      economic: 4,
    },
    {
      category: 'train',
      other: 5,
      firstClass: 3,
    },
  ];
});

// Build series array first (will be used to extract mapping)
const seriesArray = computed(() => {
  return [
    {
      name: 'business',
      key: 'business',
      itemStyle: {
        color: props.colorScheme.default,
      },
    },
    {
      name: 'economic',
      key: 'economic',
      itemStyle: {
        color: props.colorScheme.default,
      },
    },
    {
      name: 'other',
      key: 'other',
      itemStyle: {
        color: props.colorScheme.dark,
      },
    },
    {
      name: 'first class',
      key: 'firstClass',
      itemStyle: {
        color: props.colorScheme.dark,
      },
    },
  ];
});

const treemapData = computed(() => {
  return datasetSource.value.map((item) => {
    const children: Array<{
      name: string;
      value: number;
      itemStyle?: { color: string };
    }> = [];
    let totalValue = 0;

    // Explicitly specify each element using seriesArray configuration
    seriesArray.value.forEach((series) => {
      const value = item[series.key as keyof typeof item] as number | undefined;
      if (value && value > 0) {
        children.push({
          name: series.name,
          value,
          itemStyle: series.itemStyle,
        });
        totalValue += value;
      }
    });

    return {
      name: item.category,
      value: totalValue,
      children,
    };
  });
});

const chartOption = computed((): EChartsOption => {
  return {
    backgroundColor: 'transparent',
    grid: {
      top: 0,
      bottom: 0,
      left: 0,
      right: 0,
      containLabel: false,
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as {
          name?: string;
          value?: number;
          treePathInfo?: Array<{ name: string }>;
        };
        const name = p.name || '';
        const value = p.value || 0;
        const path = p.treePathInfo?.map((item) => item.name) || [name];

        let tooltip = `<strong>${path.join(' / ')}</strong><br/>`;
        tooltip += `Value: <strong>${value.toFixed(1)}</strong>`;

        return tooltip;
      },
    },
    dataset: {
      dimensions: ['category', 'business', 'economic', 'other', 'firstClass'],
      source: datasetSource.value as Array<Record<string, unknown>>,
    },
    series: [
      {
        type: 'treemap',
        data: treemapData.value,
        roam: false,
        nodeClick: false,
        breadcrumb: {
          show: false,
        },
        left: 0,
        right: 0,
        top: 0,
        bottom: 0,
        width: '100%',
        height: '100%',
        label: {
          show: true,
          formatter: '{b}',
          fontSize: 14,
          fontWeight: 'bold',
          color: 'black',
        },
        upperLabel: {
          show: true,
          height: 0,
          color: 'black',
        },
        itemStyle: {
          borderColor: 'transparent',
          borderWidth: 0,
          gapWidth: 1,
        },
        emphasis: {
          itemStyle: {
            borderColor: 'transparent',
            borderWidth: 0,
          },
          label: {
            show: true,
            fontSize: 16,
            color: 'black',
          },
        },
        levels: [
          {
            // Top level (plane, train)
            itemStyle: {
              borderColor: 'transparent',
              borderWidth: 0,
              gapWidth: 1,
            },
            upperLabel: {
              show: true,
              fontSize: 16,
              fontWeight: 'bold',
              color: '#333',
              height: 0,
            },
            label: {
              show: true,
              fontSize: 14,
              color: props.colorScheme.darker,
            },
            colorSaturation: [0.1, 0.6],
            colorMappingBy: 'value',
            visualMin: 0,
            visualMax: 10,
          },
          {
            // Second level (business, economic, other, first class)
            itemStyle: {
              borderColor: 'transparent',
              borderWidth: 0,
              gapWidth: 1,
            },
            upperLabel: {
              show: false,
            },
            label: {
              show: true,
              fontSize: 12,
              color: '#333',
            },
            colorSaturation: [0.4, 0.7],
            colorMappingBy: 'value',
            visualMin: 0,
            visualMax: 6,
          },
        ],
      },
    ],
  };
});

const chartRef = ref<InstanceType<typeof VChart>>();
</script>

<template>
  <q-card-section class="flex justify-between items-center q-pb-none">
    <div>
      <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
        {{ $t('treemap_module_chart_title') }}
      </span>
    </div>

    <div></div>
  </q-card-section>
  <q-card-section class="chart-container q-pa-none">
    <v-chart ref="chartRef" class="chart" autoresize :option="chartOption" />
  </q-card-section>
</template>

<style scoped>
.chart {
  width: 100%;
  height: 250px;
}

.chart-container {
  padding: 0 !important;
  margin: 0 !important;
}

.chart :deep(canvas) {
  display: block;
}
</style>
