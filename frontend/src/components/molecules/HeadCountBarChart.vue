<script lang="ts" setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
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
import TooltipEcharts from '@/components/charts/results/TooltipEcharts.vue';
import { useEchartsTooltip } from '@/components/charts/results/useEchartsTooltip';

import { colors } from '@/constant/charts';
import { MODULES } from '@/constant/modules';
import {
  getHeadcountChartKeys,
  resolveHeadcountCategoryLabel,
} from '@/utils/headcountChart';
import { getDataEntryTaxonomy } from '@/api/taxonomies';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
]);

const { t, locale } = useI18n();
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
    year?: number | string | null;
  }>(),
  {
    stats: () => ({}),
    year: null,
  },
);
const OVERRIDE = false;
const HEADCOUNT_COLOR = colors.value.yellow.darker;
const HEADCOUNT_FILL = colors.value.yellow.default;
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

const chartKeys = computed(() => getHeadcountChartKeys(props.stats));

// SIUS code -> request-locale label, from the member taxonomy vocabulary
// (#2613, same source ModuleTable/ModuleForm use). The chart fetches its
// own copy: unlike the table it also renders on the Results page, where
// the member submodule taxonomy may never have been loaded.
const suisLabels = ref<Record<string, string>>({});

async function loadSuisLabels() {
  if (!props.year) return;
  try {
    const taxonomy = await getDataEntryTaxonomy(
      MODULES.Headcount,
      'member',
      props.year,
    );
    const map: Record<string, string> = {};
    taxonomy.children?.forEach((node) => {
      if (node.name && node.label) map[node.name] = node.label;
    });
    suisLabels.value = map;
  } catch {
    // Chart stays usable with bare codes; labels arrive on next load.
  }
}

// Locale-dependent, like the vocabulary itself (same pattern as ModuleTable).
watch(locale, loadSuisLabels);
watch(() => props.year, loadSuisLabels);
onMounted(loadSuisLabels);

// Students have no SIUS code — they keep the module's own i18n label.
function categoryLabel(key: string): string {
  return resolveHeadcountCategoryLabel(
    key,
    suisLabels.value,
    t(`${MODULES.Headcount}-student-table-title`),
  );
}

const chartOptions = computed<EChartsOption>(() => {
  const keys = chartKeys.value;

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
              color: HEADCOUNT_COLOR,
            },
          ],
        });
        return '';
      },
    },
    legend: { show: false },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '5%',
      containLabel: true,
    },
    dataset: {
      dimensions: ['category', 'value'],
      source: keys.map((key) => ({
        category: categoryLabel(key),
        value: Math.round((props.stats?.[key] ?? 0) * 10) / 10,
      })),
    },
    xAxis: {
      type: 'category',
      axisLabel: {
        interval: 0,
        fontSize: 11,
        width: 90,
        overflow: 'break',
        lineHeight: 14,
        hideOverlap: false,
      },
    },
    yAxis: { type: 'value', boundaryGap: [0, 0.01] },
    series: [
      {
        type: 'bar',
        encode: { x: 'category', y: 'value' },
        barMaxWidth: 100,
        itemStyle: {
          color: (params) => {
            // const key = keys[params.dataIndex];
            // return colorMap[key] || '#00a79f';
            if (OVERRIDE) {
              const key = keys[params.dataIndex];
              return colorMap[key] || HEADCOUNT_COLOR;
            }
            return HEADCOUNT_FILL;
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
  height: 320px;
}
</style>
