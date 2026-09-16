<template>
  <div class="harness">
    <ModuleCarbonFootprintChart
      :breakdown-data="breakdownData"
      :bordered="false"
      :enforce-module-activation="false"
      hide-header
      hide-actions
    />
    <pre data-testid="axis-name-layout">{{ layoutJson }}</pre>
    <pre data-testid="axis-name-diagnostics">{{ diagnostics }}</pre>
  </div>
</template>

<script lang="ts">
/** Axis-aligned box of one rendered text, in canvas pixels. */
export interface TextRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Where the y-axis name and its tick labels landed on the canvas. */
export interface AxisNameLayout {
  canvasWidth: number;
  name: TextRect;
  labels: TextRect[];
}
</script>

<script setup lang="ts">
// Test-only driver for chart-axis-name-overlap.spec.ts. Mounts the real
// Results bar chart with one billion-scale bar, then reads where ECharts
// drew the y-axis name and the numeric tick labels. Same rationale as the
// other harnesses: `@/...` imports resolve in the CT Vite bundle, not in the
// spec file's Node loader.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { getInstanceByDom } from 'echarts/core';
import type { ECharts } from 'echarts/core';
import ModuleCarbonFootprintChart from '@/components/charts/results/ModuleCarbonFootprintChart.vue';
import type { EmissionBreakdownResponse } from '@/stores/modules';

// The bug's input: totals in the billions widen the tick labels
// ("165,000,000,000") far past the 40px gap the name used to sit in.
const BILLION_SCALE_TONNES = 165_000_000_000;
const AXIS_NAME = 't CO₂-eq';
const NUMERIC_LABEL = /^[\d,.\s']+$/;

const breakdownData: EmissionBreakdownResponse = {
  module_breakdown: [
    {
      category: 'professional_travel',
      category_key: 'professional_travel',
      scope: 3,
      plane: BILLION_SCALE_TONNES,
      emissions: [],
      parent_keys_order: [],
    },
  ],
  additional_breakdown: [],
  per_person_breakdown: {},
  validated_categories: ['professional_travel'],
  headcount_validated: false,
  buildings_validated: false,
  total_tonnes_co2eq: BILLION_SCALE_TONNES,
  total_fte: 1,
};

const layout = ref<AxisNameLayout | null>(null);
const diagnostics = ref('waiting for the chart to render');
const layoutJson = computed(() =>
  layout.value ? JSON.stringify(layout.value) : '',
);

// zrender's displayables: only the text-carrying bits are read here.
interface ZrText {
  style?: { text?: unknown };
  transform?: number[] | null;
  getBoundingRect(): {
    clone(): {
      x: number;
      y: number;
      width: number;
      height: number;
      applyTransform(m: number[]): void;
    };
  };
}

function worldRect(el: ZrText): TextRect {
  const rect = el.getBoundingRect().clone();
  if (el.transform) rect.applyTransform(el.transform);
  return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
}

function readLayout(chart: ECharts): AxisNameLayout | null {
  const zr = chart.getZr() as unknown as {
    storage: { getDisplayList(update?: boolean): ZrText[] };
  };
  const texts = zr.storage
    .getDisplayList(true)
    .filter((el) => typeof el.style?.text === 'string');
  const name = texts.find((el) => el.style?.text === AXIS_NAME);
  const labels = texts.filter((el) =>
    NUMERIC_LABEL.test(String(el.style?.text)),
  );
  diagnostics.value = `texts on canvas: ${texts
    .map((el) => JSON.stringify(el.style?.text))
    .join(', ')}`;
  // The value axis draws several ticks; fewer means the chart is mid-render.
  if (!name || labels.length < 2) return null;
  return {
    canvasWidth: chart.getWidth(),
    name: worldRect(name),
    labels: labels.map(worldRect),
  };
}

let timer: ReturnType<typeof setInterval> | undefined;

onMounted(() => {
  timer = setInterval(() => {
    const dom = document.querySelector('[_echarts_instance_]');
    const chart = dom ? getInstanceByDom(dom as HTMLElement) : undefined;
    if (!chart) {
      diagnostics.value = 'no ECharts instance mounted yet';
      return;
    }
    const next = readLayout(chart);
    if (!next) return;
    layout.value = next;
    clearInterval(timer);
  }, 100);
});

onBeforeUnmount(() => clearInterval(timer));
</script>

<style scoped>
.harness {
  width: 900px;
}
</style>
