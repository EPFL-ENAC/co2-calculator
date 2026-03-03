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
import { formatTonnesForChart } from 'src/utils/number';
import type { EmissionTreemapCategory } from 'src/composables/useEmissionTreemap';

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
  data: EmissionTreemapCategory[];
  height?: string;
  showEvolutionDialog?: boolean;
}>();

const treemapData = computed(() => {
  return props.data
    .filter((item) => item.value > 0 && item.children.length > 0)
    .map((item) => ({
      name: t(item.name, item.name),
      value: item.value,
      itemStyle: { color: item.color },
      children: item.children
        .filter((c) => c.value > 0)
        .map((c) => ({
          name:
            c.percentage !== undefined
              ? `${t(c.name, c.name)} (${Math.round(c.percentage)}%)`
              : t(c.name, c.name),
          value: c.value,
          itemStyle: { color: item.color },
        })),
    }));
});

const legendData = computed(() =>
  props.data
    .filter((item) => item.value > 0)
    .map((item) => ({ name: t(item.name, item.name), color: item.color })),
);

const chartOption = computed(
  (): EChartsOption => ({
    backgroundColor: 'transparent',
    grid: { top: 0, bottom: 0, left: 0, right: 0, containLabel: false },
    legend: { show: false },
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as {
          name?: string;
          value?: number;
          treePathInfo?: Array<{ name: string }>;
          itemStyle?: { color?: string };
          color?: string;
          data?: { name?: string; itemStyle?: { color?: string } };
        };

        const name = p.name ?? p.data?.name ?? '';
        const value = p.value ?? 0;
        const color =
          p.data?.itemStyle?.color ??
          p.itemStyle?.color ??
          p.color ??
          '#999999';

        // Resolve category name by walking treemapData
        let categoryName = '';
        let displayName = name;

        for (const cat of treemapData.value) {
          if (cat.name === name) {
            categoryName = cat.name;
            displayName = cat.name;
            break;
          }
          const child = cat.children.find((c) => {
            const base = c.name.split(' (')[0];
            const nameBase = name.split(' (')[0];
            return c.name === name || base === nameBase;
          });
          if (child) {
            categoryName = cat.name;
            displayName = child.name;
            break;
          }
        }

        // Fallback to treePathInfo
        if (!categoryName) {
          const path = p.treePathInfo?.map((i) => i.name) ?? [];
          categoryName = path[0] ?? name;
          displayName = path[path.length - 1] ?? name;
        }

        return (
          `<span style="display:inline-block;margin-right:5px;border-radius:10px;` +
          `width:10px;height:10px;background-color:${color};"></span>` +
          `<strong>${categoryName}</strong><br/>` +
          `${displayName}: <strong>${formatTonnesForChart(value)}</strong>`
        );
      },
    },
    series: [
      {
        type: 'treemap',
        data: treemapData.value,
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
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
          color: 'white',
        },
        upperLabel: { show: true, height: 0, color: 'white' },
        itemStyle: { borderColor: 'transparent', borderWidth: 0, gapWidth: 1 },
        emphasis: {
          itemStyle: { borderColor: 'transparent', borderWidth: 0 },
          label: { show: true, fontSize: 16, color: 'white' },
        },
        sort: false,
        levels: [
          {
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
            label: { show: true, fontSize: 14, color: '#333' },
          },
          {
            itemStyle: {
              borderColor: 'transparent',
              borderWidth: 0,
              gapWidth: 1,
            },
            upperLabel: { show: false },
            label: { show: true, fontSize: 12, color: '#333' },
          },
        ],
      },
    ],
  }),
);

const chartRef = ref<InstanceType<typeof VChart>>();
const showEvolutionDialogRef = ref(false);

const hasMultipleYears = computed(() => {
  const evolutionData = moduleStore.state.travelEvolutionOverTime as Array<{
    year: number;
  }>;
  if (!evolutionData?.length) return false;
  const years = new Set(evolutionData.map((i) => i.year).filter(Boolean));
  return years.size > 1;
});

watch(
  () => workspaceStore.selectedUnit?.id,
  (unitId) => {
    if (unitId && props.showEvolutionDialog) {
      moduleStore.getTravelEvolutionOverTime(unitId);
    }
  },
  { immediate: true },
);

const isEvolutionDialogOpen = computed({
  get: () => showEvolutionDialogRef.value,
  set: (v: boolean) => {
    showEvolutionDialogRef.value = v;
  },
});

// The evolution dialog always uses babyBlue (professional travel color)
const babyBlueScheme = computed(() => {
  // Access a color from the first category that has data, or fallback
  const first = props.data[0];
  return first
    ? {
        darker: first.color,
        dark: first.color,
        default: first.color,
        light: first.color,
        lighter: first.color,
      }
    : {
        darker: '#A2CBED',
        dark: '#B6D8F4',
        default: '#CDE5FA',
        light: '#D9E8F8',
        lighter: '#E5F2FC',
      };
});
</script>

<template>
  <div class="flex justify-between items-center">
    <q-card-section
      v-if="legendData.length > 0"
      class="legend-container q-pa-none"
    >
      <div class="flex flex-wrap" style="gap: 15px">
        <div
          v-for="item in legendData"
          :key="item.name"
          class="legend-item flex items-center"
        >
          <span
            class="legend-color"
            :style="{ backgroundColor: item.color }"
          ></span>
          <span class="legend-label">{{ item.name }}</span>
        </div>
      </div>
    </q-card-section>
    <q-btn
      v-if="showEvolutionDialog"
      color="primary"
      unelevated
      no-caps
      outline
      icon="o_timeline"
      size="sm"
      :label="$t('evolution_over_time')"
      class="text-weight-medium q-mb-sm"
      :disable="!hasMultipleYears"
      :title="
        !hasMultipleYears
          ? $t('evolution_over_time_requires_multiple_years')
          : ''
      "
      @click="isEvolutionDialogOpen = true"
    />
  </div>

  <q-card-section class="chart-container q-pa-none">
    <v-chart
      ref="chartRef"
      class="chart"
      autoresize
      :option="chartOption"
      :style="{ height: height ?? '200px' }"
    />
  </q-card-section>

  <q-dialog v-model="isEvolutionDialogOpen" class="evolution-dialog">
    <q-card style="width: 700px; max-width: 80vw">
      <q-card-section class="row items-center q-py-md">
        <div class="text-h4 text-weight-medium">
          {{ $t('evolution_over_time') }}
        </div>
        <q-space />
        <q-btn v-close-popup icon="close" flat round dense />
      </q-card-section>
      <q-separator />
      <q-card-section>
        <EvolutionOverTimeChart :color-scheme="babyBlueScheme" />
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<style scoped>
.chart {
  width: 100%;
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

.legend-container {
  padding-top: 8px !important;
  padding-bottom: 8px !important;
}

.legend-item {
  gap: 6px;
}

.legend-color {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
  flex-shrink: 0;
}

.legend-label {
  font-size: 12px;
  color: #333;
}
</style>
