<script setup lang="ts">
import { computed, ref, watch } from 'vue';
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
import EvolutionOverTimeChart from './EvolutionOverTimeChart.vue';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

const { t } = useI18n();
const moduleStore = useModuleStore();
const workspaceStore = useWorkspaceStore();

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
  showEvolutionDialog?: boolean;
}>();

const treemapData = computed(() => {
  const colorKeys: Array<'lighter' | 'light' | 'default' | 'dark' | 'darker'> =
    ['darker', 'dark', 'default', 'light', 'lighter'];

  if (!props.datasetSource || props.datasetSource.length === 0) {
    console.log('TreeMapModuleChart - No datasetSource data available');
    return [];
  }

  const sourceData = props.datasetSource as Array<{
    name: string;
    value: number;
    children?: Array<{ name: string; value: number; percentage?: number }>;
  }>;

  console.log('TreeMapModuleChart - Processing sourceData:', sourceData);

  const result = sourceData
    .filter((item) => {
      // Filter out items that don't have the required structure
      const hasValidStructure =
        item &&
        item.name &&
        item.value !== undefined &&
        Array.isArray(item.children);
      if (!hasValidStructure) {
        console.warn('TreeMapModuleChart - Invalid item structure:', item);
      }
      return hasValidStructure;
    })
    .map((item, index) => {
      const categoryIndex = Math.min(index, colorKeys.length - 1);
      const color = props.colorScheme[colorKeys[categoryIndex] || 'default'];

      // item.children is guaranteed to exist due to filter above
      const children = (item.children || [])
        .filter((child) => child && child.value && child.value > 0)
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

  console.log('TreeMapModuleChart - Final treemapData result:', result);
  console.log('TreeMapModuleChart - Final result length:', result.length);

  return result;
});

// Extract categories with their colors for the legend
const legendData = computed(() => {
  return treemapData.value.map((item) => ({
    name: item.name,
    color:
      (item.itemStyle as { color?: string })?.color ||
      props.colorScheme.default,
  }));
});

const chartOption = computed((): EChartsOption => {
  return {
    backgroundColor: 'transparent',
    grid: {
      top: 0,
      bottom: legendData.value.length > 0 ? 50 : 0,
      left: 0,
      right: 0,
      containLabel: false,
    },
    legend: {
      show: legendData.value.length > 0,
      data: legendData.value.map((item) => ({
        name: item.name,
        itemStyle: {
          color: item.color,
        },
      })),
      bottom: 5,
      orient: 'horizontal',
      itemGap: 15,
      textStyle: {
        fontSize: 12,
        color: '#333',
      },
      type: 'scroll',
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as {
          name?: string;
          value?: number;
          treePathInfo?: Array<{ name: string }>;
          color?: string;
          itemStyle?: { color?: string };
          data?: { name?: string };
        };
        const name = p.name || p.data?.name || '';
        const value = p.value || 0;

        const path = p.treePathInfo?.map((item) => item.name) || [];
        const color =
          p.itemStyle?.color || p.color || props.colorScheme.default;

        const allData = treemapData.value;
        let categoryName = '';
        let className = name;

        // Always search through categories to find the correct parent
        for (const category of allData) {
          if (category.children) {
            // Check if this name matches any child in this category
            const matchingChild = category.children.find((c) => {
              const childBase = c.name?.split(' (')[0];
              const nameBase = name.split(' (')[0];
              return c.name === name || childBase === nameBase;
            });
            if (matchingChild) {
              categoryName = category.name;
              className = matchingChild.name || name;
              break;
            }
          }
          // Check if name matches the category itself
          if (category.name === name) {
            categoryName = category.name;
            className = category.name;
            break;
          }
        }

        // If path has multiple levels and we didn't find a match, use path
        if (!categoryName && path.length > 1) {
          categoryName = t(path[0], path[0]);
          className = t(path[path.length - 1], path[path.length - 1]);
        }

        // Final fallback
        if (!categoryName) {
          categoryName = path.length > 0 ? t(path[0], path[0]) : name;
        }

        let tooltip = `<span style="display:inline-block;margin-right:5px;border-radius:10px;width:10px;height:10px;background-color:${color};"></span><strong>${categoryName}</strong><br/>`;
        tooltip += `${className}: <strong>${value.toFixed(0)}</strong>`;

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
        bottom: legendData.value.length > 0 ? 50 : 0,
        width: '100%',
        height: '100%',
        label: {
          show: true,
          formatter: '{b}',
          fontSize: 14,
          fontWeight: 'bold',
          color: 'white',
        },
        upperLabel: {
          show: true,
          height: 0,
          color: 'white',
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
            color: 'white',
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
const showEvolutionDialogRef = ref(false);

// Check if evolution data has multiple years
const hasMultipleYears = computed(() => {
  const evolutionData = moduleStore.state.travelEvolutionOverTime as Array<{
    year: number;
    transport_mode: string;
    kg_co2eq: number;
  }>;

  if (!evolutionData || evolutionData.length === 0) {
    return false;
  }

  const uniqueYears = new Set<number>();
  evolutionData.forEach((item) => {
    if (item.year) {
      uniqueYears.add(item.year);
    }
  });

  return uniqueYears.size > 1;
});

// Fetch evolution data when component mounts or unit changes
watch(
  () => workspaceStore.selectedUnit?.id,
  (unitId) => {
    if (unitId) {
      moduleStore.getTravelEvolutionOverTime(unitId);
    }
  },
  { immediate: true },
);

const showEvolutionButton = computed(() => props.showEvolutionDialog ?? true);

const isEvolutionDialogOpen = computed({
  get: () => showEvolutionDialogRef.value,
  set: (value: boolean) => {
    showEvolutionDialogRef.value = value;
  },
});
</script>

<template>
  <div class="flex justify-end">
    <q-btn
      v-if="showEvolutionButton"
      color="primary"
      unelevated
      no-caps
      outline
      icon="o_timeline"
      size="sm"
      label="Evolution over time"
      class="text-weight-medium q-mb-sm"
      :disable="!hasMultipleYears"
      :title="
        !hasMultipleYears
          ? 'Evolution over time requires data from multiple years'
          : ''
      "
      @click="isEvolutionDialogOpen = true"
    />
  </div>
  <q-card-section class="chart-container q-pa-none">
    <v-chart ref="chartRef" class="chart" autoresize :option="chartOption" />
  </q-card-section>

  <q-dialog v-model="isEvolutionDialogOpen" class="evolution-dialog">
    <q-card>
      <q-card-section class="row items-center q-py-md">
        <div class="text-h4 text-weight-medium">Evolution over time</div>
        <q-space />
        <q-btn v-close-popup icon="close" flat round dense />
      </q-card-section>
      <q-separator />
      <q-card-section>
        <EvolutionOverTimeChart :color-scheme="colorScheme" />
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<style scoped>
.chart {
  width: 100%;
  height: 280px;
  overflow: visible;
}

.chart-container {
  padding: 0 !important;
  margin: 0 !important;
  overflow: visible;
}

.chart :deep(canvas) {
  display: block;
}

.evolution-dialog :deep(.q-dialog__inner) {
  max-width: 900px;
}
</style>
