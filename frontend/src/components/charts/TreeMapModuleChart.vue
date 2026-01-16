<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { TreemapChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';

const { t } = useI18n();

use([
  CanvasRenderer,
  TreemapChart,
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
  datasetSource: Array<Record<string, unknown>>;
}>();

const treemapData = computed(() => {
  const colorKeys: Array<'lighter' | 'light' | 'default' | 'dark' | 'darker'> =
    ['lighter', 'light', 'default', 'dark', 'darker'];

  return (
    props.datasetSource as Array<{
      name: string;
      value: number;
      children: Array<{ name: string; value: number; percentage?: number }>;
    }>
  )
    .map((item, index) => {
      const categoryIndex = Math.min(index, colorKeys.length - 1);
      const color = props.colorScheme[colorKeys[categoryIndex] || 'default'];

      const children = item.children
        .filter((child) => child.value && child.value > 0)
        .map((child) => ({
          name:
            child.percentage !== undefined
              ? `${t(child.name, child.name)} (${Math.round(child.percentage)}%)`
              : t(child.name, child.name),
          value: child.value,
          itemStyle: { color },
        }));

      return {
        name: t(item.name, item.name),
        value: item.value,
        children,
        itemStyle: { color },
        _sortIndex: index,
      };
    })
    .filter((item) => item.value > 0 && item.children.length > 0);
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

        const translatedPath = path.map((name) => {
          // Try to translate the name, fallback to original if translation not found
          const translation = t(name, name);
          return translation;
        });

        let tooltip = `<strong>${translatedPath.join(' / ')}</strong><br/>`;
        tooltip += `Value: <strong>${value.toFixed(1)}</strong>`;

        return tooltip;
      },
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
        sort: false,
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
