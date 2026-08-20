<template>
  <div :class="isPrintMode ? 'q-pa-none' : 'q-pa-lg'">
    <div class="row items-center justify-between q-mb-md">
      <div
        class="text-weight-medium"
        :class="isPrintMode ? 'text-body1' : 'text-h5'"
      >
        {{ title }}
      </div>
      <q-checkbox
        v-if="!isPrintMode"
        v-model="showAdditional"
        :label="$t('results_module_carbon_toggle_additional_data')"
        size="sm"
        dense
      />
    </div>
    <v-chart
      ref="chartRef"
      class="planner-grant-comparison-chart"
      :class="{ 'planner-grant-comparison-chart--print': isPrintMode }"
      :option="chartOption"
      autoresize
    />
    <div v-if="!isPrintMode" class="row q-gutter-sm q-mt-sm">
      <q-btn
        outline
        no-caps
        size="sm"
        icon="o_download"
        :label="$t('common_download_as_png')"
        @click="downloadPNG"
      />
      <q-btn
        outline
        no-caps
        size="sm"
        icon="o_download"
        :label="$t('common_download_as_csv')"
        @click="downloadCSV"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components';
import type { EChartsOption, SeriesOption } from 'echarts';
import VChart from 'vue-echarts';
import { getCssVar } from 'quasar';
import { useI18n } from 'vue-i18n';

import {
  CHART_CATEGORY_COLOR_SCALES,
  RESULTS_CATEGORY_LABEL_KEYS,
  RESULTS_SUBCATEGORY_LABEL_KEYS,
} from 'src/constant/charts';
import type { EmissionBreakdownResponse } from 'src/stores/modules';
import { downloadEchartAsPng } from 'src/utils/chartDownload';
import { downloadCsv, escapeCsvValue } from 'src/utils/csvDownload';
import { withYearRange } from 'src/utils/plannerYearRange';
import { usePrintMode } from 'src/composables/print/usePrintMode';

/**
 * Grant Proposal vs effective (year-by-year) results, two bars per
 * category (#1977). The two views count the same project, so they sit side
 * by side and are never summed together. Each bar keeps the Results chart's
 * look: the category's color, cut into subcategory segments by shade; the
 * effective bars carry a hatch decal to tell the pair apart.
 */

type CategoryRow = Record<string, unknown> & {
  category?: unknown;
  category_key?: unknown;
  parent_keys_order?: string[];
};

const props = defineProps<{
  title: string;
  grantBreakdown: EmissionBreakdownResponse | null;
  yearsBreakdown: EmissionBreakdownResponse | null;
  /** The plan's full range, shown after the Grant Proposal label. */
  grantYearRange?: string;
  /** The filled-years range, shown after the Effective label. */
  effectiveYearRange?: string;
}>();

use([
  CanvasRenderer,
  BarChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
]);

const { t } = useI18n();
const isPrintMode = usePrintMode();

const showAdditional = ref(isPrintMode.value);

// The Results charts' categories, in their shared order.
const MAIN_CATEGORY_KEYS = [
  'process_emissions',
  'buildings_energy_combustion',
  'buildings_room',
  'equipment',
  'external_cloud_and_ai',
  'professional_travel',
  'purchases',
  'research_facilities',
] as const;
const ADDITIONAL_CATEGORY_KEYS = [
  'commuting',
  'food',
  'waste',
  'embodied_energy',
] as const;

const categoryKeys = computed<string[]>(() =>
  showAdditional.value
    ? [...MAIN_CATEGORY_KEYS, ...ADDITIONAL_CATEGORY_KEYS]
    : [...MAIN_CATEGORY_KEYS],
);

function rowOf(
  breakdown: EmissionBreakdownResponse | null,
  key: string,
): CategoryRow | undefined {
  if (!breakdown) return undefined;
  const rows = [
    ...breakdown.module_breakdown,
    ...breakdown.additional_breakdown,
  ] as CategoryRow[];
  return rows.find((row) => String(row.category_key ?? row.category) === key);
}

/** Segment keys of a category, ordered, across both views. */
function segmentsOf(
  grant: CategoryRow | undefined,
  years: CategoryRow | undefined,
) {
  const segments: string[] = [];
  for (const key of [
    ...(grant?.parent_keys_order ?? []),
    ...(years?.parent_keys_order ?? []),
  ]) {
    if (!segments.includes(key)) segments.push(key);
  }
  return segments;
}

function segmentValue(row: CategoryRow | undefined, segment: string): number {
  const value = Number(row?.[segment] ?? 0);
  return Number.isFinite(value) ? value : 0;
}

const SHADE_ORDER = ['darker', 'dark', 'default', 'light', 'lighter'] as const;

// Same fallback convention as the main chart: an unmapped key shows raw.
function segmentLabel(segment: string): string {
  const key = RESULTS_SUBCATEGORY_LABEL_KEYS[segment];
  return key ? t(key) : segment;
}

const YEARS_DECAL = {
  symbol: 'line',
  rotation: Math.PI / 4,
  dashArrayX: [1, 0],
  dashArrayY: [4, 3],
  color: 'rgba(255, 255, 255, 0.7)',
};

const grantLabel = computed(() =>
  withYearRange(t('planner_project_grant_title'), props.grantYearRange ?? ''),
);
const yearsLabel = computed(() =>
  withYearRange(
    t('planner_results_series_years'),
    props.effectiveYearRange ?? '',
  ),
);

function totalsOf(view: 'grant' | 'years'): number[] {
  const breakdown =
    view === 'grant' ? props.grantBreakdown : props.yearsBreakdown;
  return categoryKeys.value.map((key) => {
    const row = rowOf(breakdown, key);
    return (row?.parent_keys_order ?? []).reduce(
      (sum, segment) => sum + segmentValue(row, segment),
      0,
    );
  });
}

const chartOption = computed<EChartsOption>(() => {
  const infoColor = getCssVar('info') ?? undefined;
  const series: SeriesOption[] = [];

  categoryKeys.value.forEach((catKey, catIdx) => {
    const scale = CHART_CATEGORY_COLOR_SCALES.value[catKey];
    const grantRow = rowOf(props.grantBreakdown, catKey);
    const yearsRow = rowOf(props.yearsBreakdown, catKey);

    segmentsOf(grantRow, yearsRow).forEach((segment, segIdx) => {
      const color = scale[SHADE_ORDER[segIdx % SHADE_ORDER.length]];
      const dataFor = (row: CategoryRow | undefined) =>
        categoryKeys.value.map((_, idx) =>
          idx === catIdx ? segmentValue(row, segment) : 0,
        );
      series.push({
        // All grant segments share one name so the legend shows a single
        // toggleable entry per view.
        name: grantLabel.value,
        id: `grant:${catKey}:${segment}`,
        type: 'bar',
        stack: 'grant',
        itemStyle: { color },
        data: dataFor(grantRow),
      });
      series.push({
        name: yearsLabel.value,
        id: `years:${catKey}:${segment}`,
        type: 'bar',
        stack: 'years',
        itemStyle: { color, decal: YEARS_DECAL },
        data: dataFor(yearsRow),
      });
    });
  });

  return {
    legend: {
      top: 0,
      data: [
        { name: grantLabel.value, itemStyle: { color: infoColor } },
        {
          name: yearsLabel.value,
          itemStyle: { color: infoColor, decal: YEARS_DECAL },
        },
      ],
    },
    grid: { left: 56, right: 16, top: 48, bottom: 80 },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        type Param = {
          name?: string;
          seriesId?: string;
          marker?: string;
          value?: unknown;
        };
        const list = (Array.isArray(params) ? params : [params]) as Param[];
        const first = list[0];
        const DIVIDER = '1px solid rgba(128,128,128,0.3)';
        const row = (left: string, right: string, indent = false) =>
          `<div style="display:flex;justify-content:space-between;` +
          `align-items:baseline;gap:32px;line-height:1.9;` +
          `${indent ? 'padding-left:16px;' : ''}">` +
          `<span>${left}</span>` +
          `<span style="font-variant-numeric:tabular-nums">${right}</span></div>`;
        // One block per bar: its total, then its subcategory cuts.
        const section = (label: string, prefix: string) => {
          const items = list.filter(
            (p) =>
              String(p.seriesId ?? '').startsWith(prefix) &&
              Number(p.value ?? 0) > 0,
          );
          const total = items.reduce((sum, p) => sum + Number(p.value), 0);
          return (
            `<div style="margin-top:10px">` +
            row(`<b>${label}</b>`, `<b>${total.toFixed(2)} t</b>`) +
            items
              .map((p) => {
                const segment = String(p.seriesId ?? '').split(':')[2] ?? '';
                return row(
                  `${p.marker ?? ''} ${segmentLabel(segment)}`,
                  `${Number(p.value).toFixed(2)} t`,
                  true,
                );
              })
              .join('') +
            `</div>`
          );
        };
        return (
          `<div style="min-width:240px">` +
          `<div style="font-weight:600;border-bottom:${DIVIDER};` +
          `padding-bottom:6px">` +
          `${first?.name ?? ''} <span style="font-weight:400;opacity:0.7">(t CO₂-eq)</span></div>` +
          section(grantLabel.value, 'grant:') +
          section(yearsLabel.value, 'years:') +
          `</div>`
        );
      },
    },
    xAxis: {
      type: 'category',
      data: categoryKeys.value.map((key) =>
        t(RESULTS_CATEGORY_LABEL_KEYS[key]),
      ),
      axisLabel: { rotate: 45, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 't CO₂-eq',
      nameLocation: 'middle',
      nameGap: 44,
    },
    series,
  };
});

const chartRef = ref<InstanceType<typeof VChart>>();

const downloadPNG = () =>
  downloadEchartAsPng(chartRef.value?.chart, 'planner-grant-comparison');

/** One CSV per view — a grant-proposal file and an effective file. */
const downloadCSV = () => {
  const escape = escapeCsvValue;
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const files: { name: string; view: 'grant' | 'years' }[] = [
    { name: `grant-proposal-${stamp}.csv`, view: 'grant' },
    { name: `effective-${stamp}.csv`, view: 'years' },
  ];
  const labels = categoryKeys.value.map((key) =>
    t(RESULTS_CATEGORY_LABEL_KEYS[key]),
  );
  for (const file of files) {
    const totals = totalsOf(file.view);
    const csv = [
      [t('csv_header_category'), t('csv_header_co2')].map(escape).join(','),
      ...labels.map((label, idx) => [label, totals[idx]].map(escape).join(',')),
    ].join('\n');
    downloadCsv(csv, file.name);
  }
};
</script>

<style scoped lang="scss">
.planner-grant-comparison-chart {
  width: 100%;
  height: 420px;

  &--print {
    height: 360px;
  }
}
</style>
