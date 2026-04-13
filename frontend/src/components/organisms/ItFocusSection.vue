<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import { TooltipComponent, GridComponent } from 'echarts/components';
import VChart from 'vue-echarts';

import BigNumber from 'src/components/molecules/BigNumber.vue';
import { CHART_CATEGORY_COLOR_SCHEMES, colors } from 'src/constant/charts';
import { IT_FOCUS_CATEGORY_TO_MODULE } from 'src/constant/itFocus';
import { MODULE_STATES } from 'src/constant/moduleStates';
import { useTimelineStore } from 'src/stores/modules';
import { formatTonnesCO2, formatTonnesForChart } from 'src/utils/number';
import type { ItBreakdownResponse } from 'src/stores/modules';

use([CanvasRenderer, BarChart, TooltipComponent, GridComponent]);

const props = withDefaults(
  defineProps<{
    data: ItBreakdownResponse | null;
    loading?: boolean;
    /** From results summary; used for equivalent car km (kg CO₂-eq / km). */
    co2PerKmKg?: number;
  }>(),
  {
    loading: false,
    co2PerKmKg: 0,
  },
);

const { t } = useI18n();
const timelineStore = useTimelineStore();

function isItCategoryModuleValidated(categoryKey: string): boolean {
  const mod = IT_FOCUS_CATEGORY_TO_MODULE[categoryKey];
  if (!mod) return false;
  return timelineStore.itemStates[mod] === MODULE_STATES.Validated;
}

const CATEGORY_LABEL_MAP: Record<string, string> = {
  equipment_it: 'it-focus-equipment-it',
  purchases_it: 'it-focus-purchases-it',
  external_cloud_and_ai: 'it-focus-cloud-ai',
  research_facilities_it: 'it-focus-research-facilities',
};

/** Y-axis top → bottom after chart `.reverse()` (first here = top of chart). */
const IT_FOCUS_CATEGORY_ORDER = [
  'equipment_it',
  'external_cloud_and_ai',
  'purchases_it',
  'research_facilities_it',
] as const;

const CLOUD_AI_LABEL_MAP: Record<string, string> = {
  stockage: 'it-focus-cloud-stockage',
  virtualisation: 'it-focus-cloud-virtualisation',
  calcul: 'it-focus-cloud-calcul',
  ai: 'it-focus-cloud-ai-providers',
};

/** Map category_key → single color (dark shade) */
const categoryColor = computed(() => ({
  equipment_it: colors.value.periwinkle.dark,
  purchases_it: colors.value.lightGreen.dark,
  external_cloud_and_ai:
    CHART_CATEGORY_COLOR_SCHEMES.value.external_cloud_and_ai,
  /** Same as `research_facilities` in module / results charts (CHART_CATEGORY_COLOR_SCHEMES). */
  research_facilities_it:
    CHART_CATEGORY_COLOR_SCHEMES.value.research_facilities,
}));

interface BarSegment {
  name: string;
  value: number;
  color: string;
}

interface CategoryBar {
  label: string;
  categoryKey: string;
  segments: BarSegment[];
  total: number;
  validated: boolean;
}

/**
 * Build stacked horizontal bars: one bar per IT category,
 * segments within = top items (top 3 + rest for equipment/purchases,
 * sub-breakdown for cloud & AI).
 */
const categoryBars = computed<CategoryBar[]>(() => {
  if (!props.data) return [];

  const bars: CategoryBar[] = [];

  // Index API data by key — non-validated categories may be absent from the response
  const dataByKey = Object.fromEntries(
    props.data.categories.map((c) => [c.category_key, c]),
  );

  // Iterate the fixed order so all 4 rows are always present (validated or not)
  for (const categoryKey of IT_FOCUS_CATEGORY_ORDER) {
    const validated = isItCategoryModuleValidated(categoryKey);
    const label = t(CATEGORY_LABEL_MAP[categoryKey] ?? categoryKey);
    const color =
      categoryColor.value[categoryKey as keyof typeof categoryColor.value] ??
      '#999';

    if (!validated) {
      bars.push({
        label,
        categoryKey,
        segments: [],
        total: 0,
        validated: false,
      });
      continue;
    }

    const cat = dataByKey[categoryKey];
    if (!cat || cat.tonnes_co2eq <= 0) {
      // Validated but no data: still show the row (empty bar, black label)
      bars.push({
        label,
        categoryKey,
        segments: [],
        total: 0,
        validated: true,
      });
      continue;
    }

    const items = cat.top_items ?? [];
    const segments: BarSegment[] = [];

    if (items.length === 0) {
      segments.push({ name: label, value: cat.tonnes_co2eq, color });
    } else {
      items.forEach((item) => {
        if (item.value <= 0) return;
        let name = item.name;
        if (categoryKey === 'external_cloud_and_ai') {
          name = t(CLOUD_AI_LABEL_MAP[item.name] ?? item.name);
        } else if (item.name === 'rest') {
          name = t('it-focus-rest');
        }
        segments.push({ name, value: item.value, color });
      });
    }

    bars.push({
      label,
      categoryKey,
      segments,
      total: cat.tonnes_co2eq,
      validated: true,
    });
  }

  return bars;
});

// Show chart as long as there's at least one bar (validated or grayed-out)
const hasData = computed(() => categoryBars.value.length > 0);

/** Set of translated labels for validated categories (used for axis styling). */
const validatedLabels = computed(
  () =>
    new Set(categoryBars.value.filter((b) => b.validated).map((b) => b.label)),
);

/** Tonnes from categories whose parent module is validated (aligned with visible bars). */
const displayTotalItTonnes = computed(() =>
  categoryBars.value
    .filter((b) => b.validated)
    .reduce((sum, bar) => sum + bar.total, 0),
);

/** Collect all unique segment names across all bars (union for stacking) */
const allSegmentKeys = computed(() => {
  const keys: string[] = [];
  const seen = new Set<string>();
  for (const bar of categoryBars.value) {
    for (const seg of bar.segments) {
      // Use a compound key to keep segments unique across categories
      const compoundKey = `${bar.categoryKey}__${seg.name}`;
      if (!seen.has(compoundKey)) {
        seen.add(compoundKey);
        keys.push(compoundKey);
      }
    }
  }
  return keys;
});

/** Map compound segment key → color */
const segmentColorMap = computed(() => {
  const map: Record<string, string> = {};
  for (const bar of categoryBars.value) {
    for (const seg of bar.segments) {
      map[`${bar.categoryKey}__${seg.name}`] = seg.color;
    }
  }
  return map;
});

/** Map compound segment key → display label */
const segmentLabelMap = computed(() => {
  const map: Record<string, string> = {};
  for (const bar of categoryBars.value) {
    for (const seg of bar.segments) {
      map[`${bar.categoryKey}__${seg.name}`] = seg.name;
    }
  }
  return map;
});

const chartHeight = computed(() => {
  // Always 4 rows (IT_FOCUS_CATEGORY_ORDER), validated or not
  return Math.max(200, IT_FOCUS_CATEGORY_ORDER.length * 60 + 120);
});

const barChartOption = computed<EChartsOption>(() => {
  const bars = categoryBars.value;
  if (!bars.length) return {};

  // Y axis labels (reversed so first category is at top)
  const yLabels = [...bars].reverse().map((b) => b.label);

  // Build one series per segment key (stacked)
  const series = allSegmentKeys.value.map((segKey) => ({
    name: segmentLabelMap.value[segKey] ?? segKey,
    type: 'bar' as const,
    stack: 'total',
    data: [...bars].reverse().map((bar) => {
      const seg = bar.segments.find(
        (s) => `${bar.categoryKey}__${s.name}` === segKey,
      );
      return seg ? seg.value : 0;
    }),
    itemStyle: {
      color: segmentColorMap.value[segKey] ?? '#999',
      borderColor: '#fff',
      borderWidth: 1,
    },
    barWidth: 48,
    label: { show: false },
    emphasis: {
      focus: 'series' as const,
      blurScope: 'coordinateSystem' as const,
    },
    blur: { itemStyle: { opacity: 0.4 } },
  }));

  return {
    animation: false,
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as {
          seriesName?: string;
          marker?: string;
          value?: number;
          name?: string;
        };
        const name = p.name || '';
        if (!validatedLabels.value.has(name)) {
          return `<strong>${name}</strong><br/><span style="color:#aaa">${t('results_validate_module_title', { module: name })}</span>`;
        }
        const val = Number(p.value) || 0;
        if (val <= 0) return '';
        return `${p.marker || ''} <strong>${p.seriesName || ''}</strong>: ${formatTonnesForChart(val)}${t('results_units_tonnes')}`;
      },
    },
    legend: { show: false },
    grid: {
      left: '3%',
      right: '4%',
      top: 10,
      bottom: 40,
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      name: t('tco2eq'),
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { fontSize: 11, fontWeight: 'bold' },
      axisLabel: { formatter: '{value}' },
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      axisLabel: {
        width: 150,
        overflow: 'truncate',
        formatter: (value: string) => {
          if (validatedLabels.value.has(value)) {
            return `{validated|${value}}`;
          }
          return `{unvalidated|${value}}`;
        },
        rich: {
          validated: {
            color: '#000000',
            fontSize: 10,
          },
          unvalidated: {
            color: '#aaaaaa',
            fontSize: 10,
          },
        },
      },
    },
    series: series as echarts.SeriesOption[],
  };
});
</script>

<template>
  <div>
    <div class="q-pt-xl q-px-lg">
      <h2 class="text-h2 text-weight-medium">
        {{ $t('it-title') }}
      </h2>
      <span class="text-body1 text-secondary">{{ $t('it-subtitle') }}</span>
    </div>

    <q-separator class="q-mt-xl" />

    <!-- Summary numbers -->
    <div v-if="data" class="grid-2-col q-mt-lg q-mb-lg q-px-lg">
      <BigNumber
        :title="$t('it-focus-total')"
        :number="`${formatTonnesCO2(displayTotalItTonnes)}`"
        comparison="TBD"
        color="accent"
      />
      <BigNumber
        :title="$t('it-focus-share-of-total')"
        :number="
          data.percentage_of_source_modules != null
            ? `${Math.round(data.percentage_of_source_modules)}%`
            : '-'
        "
        :comparison="$t('it-focus-share-of-total-hint')"
        hide-unit
        color="accent"
      />
    </div>

    <template v-if="!loading && data">
      <!-- Stacked horizontal bar chart - one bar per IT category, segments = top items -->

      <q-card v-if="hasData" flat bordered class="q-mb-lg q-pa-lg q-mx-lg">
        <div
          class="flex items-center no-wrap text-h5 text-weight-medium q-my-xl"
        >
          <q-icon
            name="o_info"
            size="xs"
            color="primary"
            class="cursor-pointer"
            :aria-label="$t('it-focus-breakdown-bar-title-tooltip')"
          >
            <q-tooltip
              anchor="center right"
              self="top right"
              class="u-tooltip text-body2"
              max-width="min(92vw, 48rem)"
              :offset="[8, 8]"
            >
              {{ $t('it-focus-breakdown-bar-title-tooltip') }}
            </q-tooltip>
          </q-icon>
          <span class="q-ml-sm">{{ $t('it-focus-breakdown-bar-title') }}</span>
        </div>
        <v-chart
          :option="barChartOption"
          autoresize
          :style="{ height: chartHeight + 'px', width: '100%' }"
        />
      </q-card>
    </template>

    <!-- Loading state -->
    <div v-else-if="loading" class="flex justify-center q-pa-xl">
      <q-spinner color="accent" size="40px" />
    </div>
  </div>
</template>
