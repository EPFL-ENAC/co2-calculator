<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
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

import type { EmissionTreemapCategory } from 'src/composables/useEmissionTreemap';

const { t } = useI18n();
const moduleStore = useModuleStore();
const workspaceStore = useWorkspaceStore();

const LABEL_KEY_MAP: Record<string, string> = {
  // process_emissions
  co2: 'charts-co2-subcategory',
  ch4: 'charts-ch4-subcategory',
  n2o: 'charts-n2o-subcategory',
  refrigerants: 'charts-refrigerants-subcategory',
  // buildings
  heating_thermal: 'charts-heating-thermal-subcategory',
  lighting: 'charts-lighting-subcategory',
  cooling: 'charts-cooling-subcategory',
  ventilation: 'charts-ventilation-subcategory',
  // equipment
  scientific: 'charts-scientific-subcategory',
  it: 'charts-equipment-it',
  // external cloud & AI
  stockage: 'charts-stockage-subcategory',
  virtualisation: 'charts-virtualisation-subcategory',
  calcul: 'charts-calcul-subcategory',
  provider: 'charts-ai-provider-subcategory',
  ai_provider: 'charts-ai-provider-subcategory',
  ai: 'charts-ai-provider-subcategory',
  clouds: 'charts-clouds-subcategory',
  // purchases
  scientific_equipment: 'charts-scientific-subcategory',
  it_equipment: 'charts-equipment-it',
  consumable_accessories: 'charts-consumables-subcategory',
  biological_chemical_gaseous: 'charts-bio-chemicals-subcategory',
  services: 'charts-services-subcategory',
  vehicles: 'charts-other-purchases-subcategory',
  additional: 'charts-other-purchases-subcategory',
  // research facilities
  facilities: 'charts-research-facilities-subcategory',
  animal: 'charts-research-animal-subcategory',
  // professional travel
  plane: 'charts-plane-subcategory',
  train: 'charts-train-subcategory',
  // professional travel ZZ items
  class_1: 'charts-class-1-subcategory',
  class_2: 'charts-class-2-subcategory',
  first: 'charts-first-class-subcategory',
  business: 'charts-business-class-subcategory',
  eco: 'charts-eco-class-subcategory',
};

function resolveLabel(raw: string): string {
  const key = LABEL_KEY_MAP[raw];
  return key ? t(key) : raw.replace(/_/g, ' ');
}

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
]);

const props = defineProps<{
  data: EmissionTreemapCategory[];
  height?: string;
  showEvolutionDialog?: boolean;
}>();

const visibleData = computed(() =>
  props.data.flatMap((cat) => cat.children.filter((c) => c.value > 0)),
);

const legendData = computed(() => {
  const seen = new Set<string>();
  const items: { name: string; color: string }[] = [];
  for (const child of visibleData.value) {
    // For ZZ items, show the YY parent in the legend (deduplicated).
    const legendKey = child.parentKey ?? child.name;
    if (seen.has(legendKey)) continue;
    seen.add(legendKey);
    items.push({ name: resolveLabel(legendKey), color: child.color });
  }
  return items;
});

const chartOption = computed((): EChartsOption => {
  const total = visibleData.value.reduce((s, c) => s + c.value, 0);

  const series = visibleData.value.map((cat) => {
    const pct = total > 0 ? cat.value / total : 0;
    const label = resolveLabel(cat.name);

    return {
      name: label,
      type: 'bar' as const,
      stack: 'total',
      barWidth: '100%',
      data: [{ value: pct * 100, originalValue: cat.value }],
      itemStyle: {
        color: cat.color,
        borderColor: '#fff',
        borderWidth: 1,
      },
      label: {
        show: pct >= 0.09,
        position: 'inside' as const,
        formatter: label,
        color: '#fff',
        fontWeight: 'bold' as const,
        fontSize: 13,
        backgroundColor: 'rgba(0,0,0,0.15)',
        borderRadius: 3,
        padding: [5, 10],
        overflow: 'truncate' as const,
      },
      emphasis: {
        focus: 'none' as const,
        label: {
          show: true,
          position: 'inside' as const,
          formatter: label,
          color: '#fff',
          fontWeight: 'bold' as const,
          fontSize: 13,

          overflow: 'truncate' as const,
        },
        itemStyle: {
          color: cat.color,
          borderColor: '#fff',
          borderWidth: 1,
        },
      },
      blur: {
        itemStyle: { opacity: 0.9 },
        label: { opacity: 1 },
      },
    };
  });

  return {
    animation: false,
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as {
          seriesName?: string;
          marker?: string;
          data?: { value: number; originalValue: number };
        };
        const val = p.data?.originalValue ?? 0;
        if (val <= 0) return '';
        return (
          `${p.marker || ''} <strong>${p.seriesName || ''}</strong><br/>` +
          `${p.seriesName || ''}: <strong>${val.toFixed(1)}</strong>`
        );
      },
    },
    legend: { show: false },
    grid: {
      left: 0,
      right: 0,
      top: 0,
      bottom: 0,
      containLabel: false,
    },
    yAxis: {
      type: 'category',
      data: [''],
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { show: false },
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { show: false },
      splitLine: { show: false },
    },
    series,
  };
});

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

const babyBlueScheme = computed(() => {
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
  <div class="flex justify-between items-center q-mb-xs">
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
      :key="visibleData.map((c) => c.name).join('|')"
      class="chart"
      autoresize
      :option="chartOption"
      :style="{ height: height ?? '200px' }"
    />
  </q-card-section>

  <q-dialog v-model="isEvolutionDialogOpen">
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
