<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  AriaComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';
import TooltipEcharts from './results/TooltipEcharts.vue';
import { useEchartsTooltip } from './results/useEchartsTooltip';
import { usePrintMode } from 'src/composables/print/usePrintMode';
import { downloadEchartAsPng } from 'src/utils/chartDownload';
import { useColorblindStore } from 'src/stores/colorblind';

import { buildChartDecal } from 'src/constant/charts';
import type { EmissionTreemapCategory } from 'src/composables/useEmissionTreemap';
import { formatTonnesForChart } from 'src/utils/number';

const { t } = useI18n();
const isPrintMode = usePrintMode();
const colorblindStore = useColorblindStore();

const LABEL_KEY_MAP: Record<string, string> = {
  // process_emissions
  co2: 'process-emissions.category.co2',
  ch4: 'process-emissions.category.ch4',
  n2o: 'process-emissions.category.n2o',
  refrigerants: 'process-emissions.category.refrigerants',
  refrigerant: 'process-emissions.category.refrigerants',
  // buildings
  combustion: 'charts-energy-combustion-subcategory',
  heating_thermal: 'charts-heating-thermal-subcategory',
  heating_elec: 'charts-heating-elec-subcategory',
  lighting: 'charts-lighting-subcategory',
  cooling: 'charts-cooling-subcategory',
  ventilation: 'charts-ventilation-subcategory',
  laboratories: 'charts-laboratories-subcategory',
  office: 'charts-office-subcategory',
  archives: 'charts-archives-subcategory',
  libraries: 'charts-libraries-subcategory',
  auditoriums: 'charts-auditoriums-subcategory',
  miscellaneous: 'charts-miscellaneous-subcategory',
  // equipment
  scientific: 'charts-scientific-subcategory',
  it: 'charts-equipment-it',
  other: 'charts-other-equipment-subcategory',
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
  vehicles: 'charts-vehicles-subcategory',
  other_purchases: 'charts-other-purchases-subcategory',
  additional: 'charts-additional-purchases-subcategory',
  // research facilities
  facilities: 'charts-research-facilities-subcategory',
  it_facilities: 'charts-research-it-facilities-subcategory',
  animal: 'charts-research-animal-subcategory',
  mice_and_fish_animal_facilities: 'charts-research-animal-subcategory',
  mice: 'charts-animal-mice-subcategory',
  fish: 'charts-animal-fish-subcategory',
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
  AriaComponent,
]);

const props = defineProps<{
  data: EmissionTreemapCategory[];
  height?: string;
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
    aria: {
      enabled: true,
      decal: buildChartDecal(colorblindStore.enabled),
    },
    tooltip: isPrintMode.value
      ? { show: false }
      : {
          trigger: 'item',
          formatter: (params: unknown) => {
            const p = params as {
              seriesName?: string;
              color?: string;
              data?: { value: number; originalValue: number };
            };
            const val = p.data?.originalValue ?? 0;
            if (val <= 0) {
              emitTooltip(null);
              return '';
            }
            emitTooltip({
              rows: [
                {
                  label: p.seriesName ?? '',
                  value: `${formatTonnesForChart(val)}${t('results_units_tonnes')}`,
                  color: p.color ?? '#888',
                },
              ],
            });
            return '';
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
const { tooltip, style, attach, emitTooltip } = useEchartsTooltip();

const onChartReady = async () => {
  await nextTick();
  const chart = chartRef.value?.chart;
  if (!chart) return;
  attach(chart);
};

const downloadPNG = () =>
  downloadEchartAsPng(chartRef.value?.chart, 'emission-breakdown');

defineExpose({ downloadPNG });
</script>

<template>
  <q-card-section
    v-if="!isPrintMode && legendData.length > 0"
    class="legend-container q-pa-none q-mb-xs"
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

  <q-card-section class="chart-container q-pa-none">
    <v-chart
      ref="chartRef"
      :key="`${visibleData.map((c) => c.name).join('|')}-${colorblindStore.enabled}`"
      class="chart"
      autoresize
      :option="chartOption"
      :style="{
        height: isPrintMode ? (height ?? '80px') : (height ?? '200px'),
      }"
      @vue:mounted="onChartReady"
    />
    <Teleport to="body">
      <tooltip-echarts
        v-if="tooltip.visible"
        :tooltip-state="tooltip.data"
        :style="style"
      />
    </Teleport>
  </q-card-section>
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
