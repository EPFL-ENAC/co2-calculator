<script setup lang="ts">
import { computed, type PropType, nextTick, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption, SeriesOption } from 'echarts';
import {
  buildChartDecal,
  colors,
  getChartSubcategoryColor,
  RESULTS_CATEGORY_LABEL_KEYS,
} from 'src/constant/charts';
import { useColorblindStore } from 'src/stores/colorblind';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
  AriaComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';
import TooltipEcharts from './TooltipEcharts.vue';
import { useEchartsTooltip } from './useEchartsTooltip';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
  AriaComponent,
]);

import type { EmissionBreakdownResponse } from 'src/stores/modules';
import type { TooltipRow } from 'src/types/chartTooltip';
import { formatTonnesForChart } from 'src/utils/number';
import { usePrintMode } from 'src/composables/print/usePrintMode';
import { downloadEchartAsPng } from 'src/utils/chartDownload';

const props = defineProps({
  breakdownData: {
    type: Object as PropType<EmissionBreakdownResponse | null | undefined>,
    default: undefined,
  },
  title: {
    type: String as PropType<string | undefined>,
    default: undefined,
  },

  viewAdditionalData: {
    type: Boolean as PropType<boolean | undefined>,
    default: undefined,
  },
});

const { t, locale } = useI18n();
const isPrintMode = usePrintMode();
const colorblindStore = useColorblindStore();

const toggleAdditionalData = ref(false);
const effectiveToggle = computed(
  () => props.viewAdditionalData ?? toggleAdditionalData.value,
);

function getSubcategoryColor(
  category: string,
  key: string,
  fallback: string,
): string {
  return getChartSubcategoryColor(category, key, fallback);
}

// Static map: raw category key → GHG scope
const CATEGORY_SCOPE: Record<string, 1 | 2 | 3 | 'additional'> = {
  process_emissions: 1,
  buildings_energy_combustion: 1,
  buildings_room: 2,

  equipment: 2,
  external_cloud_and_ai: 3,
  purchases: 3,
  professional_travel: 3,
  research_facilities: 3,
  commuting: 'additional',
  food: 'additional',
  waste: 'additional',
  embodied_energy: 'additional',
};

// Reverse map: translated label → raw category key (rebuilt when locale changes)
const labelToKey = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {};
  for (const [key, i18nKey] of Object.entries(CATEGORY_LABEL_MAP)) {
    map[t(i18nKey)] = key;
  }
  return map;
});

// Memoize the last scope rects to avoid redundant updates
let lastScopeState: {
  s1Left?: number;
  s2Left?: number;
  s3Left?: number;
  dividerX?: number | null;
  showAdditional: boolean;
  yZero?: number;
  locale?: string;
} | null = null;

const SCOPE_LABEL_TOP = 55;
/** Additional categories sit below scope headers to show they belong under Scope 3. */
const ADDITIONAL_LABEL_TOP = SCOPE_LABEL_TOP + 14;
const ADDITIONAL_RECT_TOP = ADDITIONAL_LABEL_TOP - 6;

function recalculateScopeRects() {
  const chart = chartRef.value?.chart;
  if (!chart) return;

  requestAnimationFrame(() => {
    updateScopeGraphics(chart);
  });
}

function updateScopeGraphics(
  chart: NonNullable<typeof chartRef.value>['chart'],
) {
  const items = datasetSource.value;
  if (items.length < 2) return;

  const getX = (label: string): number =>
    chart.convertToPixel({ xAxisIndex: 0 }, label) as number;

  const step =
    getX(String(items[1].category)) - getX(String(items[0].category));
  if (!step) return;
  const halfStep = step / 2;

  const groups: Record<string, string[]> = {
    '1': [],
    '2': [],
    '3': [],
    additional: [],
  };
  for (const item of items) {
    const label = String(item.category);
    const key = labelToKey.value[label] ?? '';
    const scope = String(CATEGORY_SCOPE[key] ?? 'additional');
    groups[scope].push(label);
  }

  const toRect = (labels: string[]) => {
    if (!labels.length) return null;
    const left = getX(labels[0]) - halfStep;
    const right = getX(labels[labels.length - 1]) + halfStep;
    return { left, width: right - left };
  };

  const s1 = toRect(groups['1']);
  const s2 = toRect(groups['2']);
  const s3 = toRect(groups['3']);
  const additionalRect = toRect(groups['additional']);
  const dividerX = groups['additional'].length
    ? getX(groups['additional'][0]) - halfStep
    : null;
  const showAdditional = effectiveToggle.value && dividerX !== null;

  // y=0 pixel (baseline) — grid bottom can drift from 0 when x-axis label height changes (e.g. FR).
  const yZero = chart.convertToPixel({ yAxisIndex: 0 }, 0) as number;
  if (!Number.isFinite(yZero)) {
    chart.setOption({ graphic: [] });
    return;
  }

  const newState = {
    s1Left: s1?.left,
    s2Left: s2?.left,
    s3Left: s3?.left,
    dividerX,
    showAdditional,
    yZero,
    locale: locale.value,
  };
  if (
    lastScopeState?.s1Left === newState.s1Left &&
    lastScopeState?.s2Left === newState.s2Left &&
    lastScopeState?.s3Left === newState.s3Left &&
    lastScopeState?.dividerX === newState.dividerX &&
    lastScopeState?.showAdditional === newState.showAdditional &&
    lastScopeState?.yZero === newState.yZero &&
    lastScopeState?.locale === newState.locale
  ) {
    return; // nothing changed — stop the loop
  }
  lastScopeState = newState;

  const scopeLabelTop = SCOPE_LABEL_TOP;
  const additionalLabelTop = ADDITIONAL_LABEL_TOP;
  const additionalRectTop = ADDITIONAL_RECT_TOP;
  // Narrow once so downstream shape/style expressions use a plain number
  // without repeated casts. The showAdditional guard already ensures
  // dividerX !== null, but TypeScript can't see through that indirection.
  const dividerXNum = Number(dividerX);

  const elements: object[] = [
    // Scope 1 label
    ...(s1
      ? [
          {
            type: 'text',
            id: 'st1',
            left: s1.left + 8,
            top: scopeLabelTop,
            style: {
              fill: '#000000',
              text: t('charts-scope') + ' 1',
              font: '11px SuisseIntl',
            },
            silent: true,
          },
        ]
      : []),
    // Scope 2 label
    ...(s2
      ? [
          {
            type: 'text',
            id: 'st2',
            left: s2.left + 8,
            top: scopeLabelTop,
            style: {
              fill: '#000000',
              text: t('charts-scope') + ' 2',
              font: '11px SuisseIntl',
            },
            silent: true,
          },
        ]
      : []),
    // Scope 3 label
    ...(s3
      ? [
          {
            type: 'text',
            id: 'st3',
            left: s3.left + 8,
            top: scopeLabelTop,
            style: {
              fill: '#000000',
              text: t('charts-scope') + ' 3',
              font: '11px SuisseIntl',
            },
            silent: true,
          },
        ]
      : []),
    // Dotted divider line between Scope 1 and Scope 2
    ...(s1 && s2
      ? [
          {
            type: 'line',
            id: 'sdiv12',
            shape: { x1: s2.left, y1: scopeLabelTop, x2: s2.left, y2: yZero },
            style: { stroke: '#aaaaaa', lineWidth: 1, lineDash: [2, 2] },
            silent: true,
          },
        ]
      : [
          {
            type: 'line',
            id: 'sdiv12',
            shape: { x1: 0, y1: 0, x2: 0, y2: 0 },
            style: { opacity: 0 },
            silent: true,
          },
        ]),
    // Dotted divider line between Scope 2 and Scope 3
    ...(s2 && s3
      ? [
          {
            type: 'line',
            id: 'sdiv23',
            shape: { x1: s3.left, y1: scopeLabelTop, x2: s3.left, y2: yZero },
            style: { stroke: '#aaaaaa', lineWidth: 1, lineDash: [2, 2] },
            silent: true,
          },
        ]
      : [
          {
            type: 'line',
            id: 'sdiv23',
            shape: { x1: 0, y1: 0, x2: 0, y2: 0 },
            style: { opacity: 0 },
            silent: true,
          },
        ]),
    // Additional categories: dashed rectangle outline + label
    ...(showAdditional && additionalRect
      ? [
          {
            type: 'rect',
            id: 'sadd',
            shape: {
              x: dividerXNum + 2,
              y: additionalRectTop,
              width: Math.max(0, additionalRect.width - 4),
              height: Math.max(0, yZero - additionalRectTop),
              r: 3,
            },
            style: {
              fill: 'transparent',
              stroke: '#888888',
              lineWidth: 1,
              lineDash: [2, 2],
            },
            silent: true,
          },
          {
            type: 'text',
            id: 'stadd',
            left: dividerXNum + 8,
            top: additionalLabelTop,
            style: {
              fill: '#000000',
              text: t('charts-additional-category'),
              font: 'italic 11px SuisseIntl',
            },
            silent: true,
          },
        ]
      : [
          {
            type: 'rect',
            id: 'sadd',
            left: 0,
            top: 0,
            shape: { width: 0, height: 0 },
            style: { opacity: 0 },
            silent: true,
          },
          {
            type: 'text',
            id: 'stadd',
            left: 0,
            top: 0,
            style: { opacity: 0, text: '' },
            silent: true,
          },
        ]),
    // Previously used elements — now cleared
    {
      type: 'rect',
      id: 'sr1',
      left: 0,
      top: 0,
      shape: { width: 0, height: 0 },
      style: { opacity: 0 },
      silent: true,
    },
    {
      type: 'rect',
      id: 'sr2',
      left: 0,
      top: 0,
      shape: { width: 0, height: 0 },
      style: { opacity: 0 },
      silent: true,
    },
    {
      type: 'rect',
      id: 'sr3',
      left: 0,
      top: 0,
      shape: { width: 0, height: 0 },
      style: { opacity: 0 },
      silent: true,
    },
    {
      type: 'rect',
      id: 'sdiv',
      left: 0,
      top: 0,
      shape: { width: 0, height: 0 },
      style: { opacity: 0 },
      silent: true,
    },
    {
      type: 'text',
      id: 'smain',
      left: 0,
      top: 0,
      style: { opacity: 0, text: '' },
      silent: true,
    },
  ];

  chart.setOption({ graphic: elements }, {
    replaceMerge: ['graphic'],
  } as Parameters<typeof chart.setOption>[1]);
}

const CATEGORY_LABEL_MAP: Record<string, string> = RESULTS_CATEGORY_LABEL_KEYS;

function translateCategory(
  entry: Record<string, unknown>,
): Record<string, unknown> {
  const cat = entry.category as string;
  const i18nKey = CATEGORY_LABEL_MAP[cat];
  return { ...entry, category: i18nKey ? t(i18nKey) : cat };
}

function normalizeCategoryRowKeys(
  entry: Record<string, unknown>,
): Record<string, unknown> {
  const cat = String(entry.category ?? entry.category_key ?? '');
  // Backend sometimes uses `other` for purchases; keep equipment `other` untouched.
  if (cat === 'purchases') {
    const next = { ...entry };
    if (next.other_purchases == null && next.other != null) {
      next.other_purchases = next.other;
    }
    // Prevent collisions with equipment's `other` series key.
    delete next.other;
    return next;
  }
  return entry;
}

function zeroNumericValues(
  entry: Record<string, unknown>,
): Record<string, unknown> {
  const next: Record<string, unknown> = { ...entry };
  Object.entries(next).forEach(([key, value]) => {
    if (key === 'category') return;
    if (typeof value === 'number' && Number.isFinite(value)) {
      next[key] = 0;
    }
  });
  return next;
}

function isCategoryValidated(category: string): boolean {
  return props.breakdownData?.validated_categories?.includes(category) ?? false;
}

function collapseByCategory(
  rows: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  const merged = new Map<string, Record<string, unknown>>();

  rows.forEach((row) => {
    const category = String(row.category ?? '');
    const existing = merged.get(category);

    if (!existing) {
      merged.set(category, { ...row });
      return;
    }

    Object.entries(row).forEach(([key, value]) => {
      if (key === 'category' || key.startsWith('__')) return;
      if (typeof value === 'object' && value !== null) return;
      const n = Number(value);
      if (!Number.isNaN(n)) {
        existing[key] = (Number(existing[key]) || 0) + n;
      } else if (existing[key] == null || existing[key] === '') {
        existing[key] = value;
      }
    });
  });

  return Array.from(merged.values());
}

function withAdditionalCategoryTotals(
  entry: Record<string, unknown>,
): Record<string, unknown> {
  const categoryKey = String(entry.category_key ?? '');
  if (
    !ADDITIONAL_HEADCOUNT_CATEGORIES.includes(categoryKey) &&
    !ADDITIONAL_BUILDINGS_CATEGORIES.includes(categoryKey)
  ) {
    return entry;
  }

  const validated = Boolean(entry.__validated);
  if (!validated) {
    // `zeroNumericValues()` doesn't touch nested emissions; force deterministic zero
    // totals for non-validated additional categories.
    return { ...entry, [categoryKey]: 0 };
  }

  const emissions = Array.isArray(entry.emissions) ? entry.emissions : [];
  const total = emissions.reduce((s, e) => {
    const v = Number((e as { value?: unknown }).value);
    return Number.isFinite(v) ? s + v : s;
  }, 0);

  // Force a deterministic total under the same key the series encodes (e.g. "waste").
  // Backend flat parent sums can be partial depending on parent_key structure.
  return { ...entry, [categoryKey]: total };
}

// Keys not translated here — moved to computed properties below
const ADDITIONAL_CATEGORY_KEY_IDS = [
  'charts-commuting-category',
  'charts-food-category',
  'charts-waste-category',
  'charts-embodied-energy-category',
];

const MAIN_CATEGORY_ORDER_IDS = [
  'charts-process-emissions-category',
  'charts-buildings-energy-combustion-category',
  'charts-buildings-room-category',
  'charts-equipment-electric-consumption-category',
  'charts-external-cloud-category',
  'charts-professional-travel-category',
  'charts-purchases-category',
  'charts-research-facilities-category',
];

const additionalCategoryKeysSet = computed(
  () => new Set(ADDITIONAL_CATEGORY_KEY_IDS.map((id) => t(id))),
);

const mainCategoryOrderMap = computed(() => {
  const map = new Map<string, number>();
  MAIN_CATEGORY_ORDER_IDS.forEach((id, idx) => {
    map.set(t(id), idx);
  });
  return map;
});

const additionalCategoryOrderMap = computed(() => {
  const map = new Map<string, number>();
  ADDITIONAL_CATEGORY_KEY_IDS.forEach((id, idx) => {
    map.set(t(id), idx);
  });
  return map;
});

const datasetSource = computed(() => {
  if (!props.breakdownData) return [];

  const baseData = collapseByCategory(
    props.breakdownData.module_breakdown
      .map((entry) => {
        const category = String(entry.category ?? '');
        return isCategoryValidated(category) ? entry : zeroNumericValues(entry);
      })
      .map(normalizeCategoryRowKeys)
      .map(translateCategory),
  );

  let allData = baseData;
  if (effectiveToggle.value) {
    const additionalData = collapseByCategory(
      props.breakdownData.additional_breakdown
        .map((entry) => {
          const category = String(entry.category ?? '');
          const validated = isCategoryValidated(category);
          if (!validated) {
            return {
              ...zeroNumericValues(entry),
              emissions: [],
              __validated: false,
            };
          }
          return { ...entry, __validated: true };
        })
        .map(withAdditionalCategoryTotals)
        .map(normalizeCategoryRowKeys)
        .map(translateCategory),
    );
    allData = [...baseData, ...additionalData];
  }

  // Partition into additional and main categories
  const additional = [];
  const main = [];
  const addSet = additionalCategoryKeysSet.value;
  for (const item of allData) {
    if (addSet.has(String(item.category))) {
      additional.push(item);
    } else {
      main.push(item);
    }
  }

  // Sort main and additional separately
  const mainMap = mainCategoryOrderMap.value;
  main.sort((a, b) => {
    const aIdx = mainMap.get(String(a.category)) ?? 999;
    const bIdx = mainMap.get(String(b.category)) ?? 999;
    return aIdx - bIdx;
  });
  const addMap = additionalCategoryOrderMap.value;
  additional.sort((a, b) => {
    const aIdx = addMap.get(String(a.category)) ?? 999;
    const bIdx = addMap.get(String(b.category)) ?? 999;
    return aIdx - bIdx;
  });

  return [...main, ...additional];
});

const EQUIPMENT_SUBKEYS = ['scientific', 'it', 'other'] as const;
const PURCHASES_SUBKEYS = [
  'scientific_equipment',
  'it_equipment',
  'consumable_accessories',
  'biological_chemical_gaseous',
  'services',
  'vehicles',
  'other_purchases',
  'additional',
] as const;

const equipPurchRankings = computed(() => {
  const findRow = (key: string) =>
    datasetSource.value.find((r) => String(r.category_key ?? '') === key);

  const rankSubkeys = (
    row: Record<string, unknown> | undefined,
    keys: readonly string[],
  ) =>
    [...keys]
      .map((k) => ({ key: k, value: Number(row?.[k] ?? 0) }))
      .sort((a, b) => b.value - a.value);

  const equipRanked = rankSubkeys(findRow('equipment'), EQUIPMENT_SUBKEYS);
  const purchAllRanked = rankSubkeys(findRow('purchases'), PURCHASES_SUBKEYS);
  const purchTop3 = purchAllRanked.slice(0, 3);
  const purchRestValue = purchAllRanked
    .slice(3)
    .reduce((s, e) => s + e.value, 0);

  return { equipRanked, purchTop3, purchRestValue };
});

const enrichedDatasetSource = computed(() => {
  const { equipRanked, purchTop3, purchRestValue } = equipPurchRankings.value;
  return datasetSource.value.map((row) => {
    const catKey = String(row.category_key ?? '');
    if (catKey === 'equipment') {
      const next = { ...row };
      EQUIPMENT_SUBKEYS.forEach((k) => {
        next[k] = 0;
      });
      equipRanked.forEach((item, i) => {
        next[`equip_rank${i + 1}`] = item.value;
      });
      return next;
    }
    if (catKey === 'purchases') {
      const next = { ...row };
      PURCHASES_SUBKEYS.forEach((k) => {
        next[k] = 0;
      });
      purchTop3.forEach((item, i) => {
        next[`purch_rank${i + 1}`] = item.value;
      });
      next['purch_rest'] = purchRestValue;
      return next;
    }
    return row;
  });
});

const additionalSeriesData = computed(() => {
  if (!effectiveToggle.value) return [];

  return [
    {
      name: t('charts-commuting-category'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: {
        x: 'category',
        y: 'commuting',
      },
      itemStyle: {
        color: colors.value.aqua.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-food-category'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: {
        x: 'category',
        y: 'food',
      },
      itemStyle: {
        color: colors.value.mint.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-waste-category'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: {
        x: 'category',
        y: 'waste',
      },
      itemStyle: {
        color: colors.value.periwinkle.darker,
      },
      label: {
        show: false,
      },
    },
    {
      name: t('charts-embodied-energy-category'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: {
        x: 'category',
        y: 'embodied_energy',
      },
      itemStyle: {
        color: colors.value.skyBlue.darker,
      },
      label: {
        show: false,
      },
    },
  ];
});

const ADDITIONAL_HEADCOUNT_CATEGORIES = ['commuting', 'food', 'waste'];

const additionalHeadcountLabels = computed(
  () =>
    new Set(
      ADDITIONAL_HEADCOUNT_CATEGORIES.map((cat) => {
        const key = CATEGORY_LABEL_MAP[cat];
        return key ? t(key) : cat;
      }),
    ),
);

const ADDITIONAL_BUILDINGS_CATEGORIES = ['embodied_energy'];

const additionalBuildingsLabels = computed(
  () =>
    new Set(
      ADDITIONAL_BUILDINGS_CATEGORIES.map((cat) => {
        const key = CATEGORY_LABEL_MAP[cat];
        return key ? t(key) : cat;
      }),
    ),
);

const validatedLabels = computed(() => {
  if (!props.breakdownData?.validated_categories) return new Set<string>();
  return new Set(
    props.breakdownData.validated_categories.map((cat) => {
      const key = CATEGORY_LABEL_MAP[cat];
      return key ? t(key) : cat;
    }),
  );
});

const chartOption = computed((): EChartsOption => {
  // Build series array first (will be used to extract mapping)
  const seriesArray = [
    // Process Emissions — YY subcategories
    {
      name: t('process-emissions.category.co2'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'co2' },
      itemStyle: {
        color: getSubcategoryColor(
          'process_emissions',
          'co2',
          colors.value.apricot.darker,
        ),
      },
      label: { show: false },
    },
    {
      name: t('process-emissions.category.ch4'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'ch4' },
      itemStyle: {
        color: getSubcategoryColor(
          'process_emissions',
          'ch4',
          colors.value.apricot.dark,
        ),
      },
      label: { show: false },
    },
    {
      name: t('process-emissions.category.n2o'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'n2o' },
      itemStyle: {
        color: getSubcategoryColor(
          'process_emissions',
          'n2o',
          colors.value.apricot.default,
        ),
      },
      label: { show: false },
    },
    {
      name: t('process-emissions.category.refrigerants'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'refrigerants' },
      itemStyle: {
        color: getSubcategoryColor(
          'process_emissions',
          'refrigerants',
          colors.value.apricot.light,
        ),
      },
      label: { show: false },
    },

    {
      name: t('charts-energy-combustion-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'combustion' },
      itemStyle: {
        color: getSubcategoryColor(
          'buildings_energy_combustion',
          'combustion',
          colors.value.lilac.light,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-heating-thermal-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'heating_thermal' },
      itemStyle: {
        color: getSubcategoryColor(
          'buildings_energy_combustion',
          'heating_thermal',
          colors.value.lilac.dark,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-heating-elec-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'heating_elec' },
      itemStyle: {
        color: getSubcategoryColor(
          'buildings_room',
          'heating_elec',
          colors.value.lilac.light,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-cooling-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'cooling' },
      itemStyle: {
        color: getSubcategoryColor(
          'buildings_room',
          'cooling',
          colors.value.lilac.dark,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-ventilation-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'ventilation' },
      itemStyle: {
        color: getSubcategoryColor(
          'buildings_room',
          'ventilation',
          colors.value.lilac.default,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-lighting-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'lighting' },
      itemStyle: {
        color: getSubcategoryColor(
          'buildings_room',
          'lighting',
          colors.value.lilac.darker,
        ),
      },
      label: { show: false },
    },
    // Equipment — top-3 subcategories sorted by emission value (descending)
    ...(() => {
      const equipSubcatLabels: Record<string, string> = {
        scientific: t('charts-scientific-subcategory'),
        it: t('charts-equipment-it'),
        other: t('charts-other-equipment-subcategory'),
      };
      return equipPurchRankings.value.equipRanked.map((item, i) => ({
        name: equipSubcatLabels[item.key] ?? item.key,
        type: 'bar' as const,
        stack: 'total',
        animation: true,
        encode: { x: 'category', y: `equip_rank${i + 1}` },
        itemStyle: {
          color: getSubcategoryColor(
            'equipment',
            item.key,
            colors.value.plum.default,
          ),
        },
        label: { show: false },
      }));
    })(),
    // Purchases — top-3 subcategories sorted by emission value + rest
    ...(() => {
      const purchSubcatLabels: Record<string, string> = {
        scientific_equipment: t('charts-scientific-subcategory'),
        it_equipment: t('charts-equipment-it'),
        consumable_accessories: t('charts-consumables-subcategory'),
        biological_chemical_gaseous: t('charts-bio-chemicals-subcategory'),
        services: t('charts-services-subcategory'),
        vehicles: t('charts-vehicles-subcategory'),
        other_purchases: t('charts-other-purchases-subcategory'),
        additional: t('charts-additional-purchases-subcategory'),
      };
      const top3Series = equipPurchRankings.value.purchTop3.map((item, i) => ({
        name: purchSubcatLabels[item.key] ?? item.key,
        type: 'bar' as const,
        stack: 'total',
        animation: true,
        encode: { x: 'category', y: `purch_rank${i + 1}` },
        itemStyle: {
          color: getSubcategoryColor(
            'purchases',
            item.key,
            colors.value.lightGreen.default,
          ),
        },
        label: { show: false },
      }));
      const restSeries = {
        name: t('charts-rest-subcategory'),
        type: 'bar' as const,
        stack: 'total',
        animation: true,
        encode: { x: 'category', y: 'purch_rest' },
        itemStyle: { color: colors.value.lightGreen.lighter },
        label: { show: false },
      };
      return [...top3Series, restSeries];
    })(),
    // External cloud & AI — YY subcategories
    {
      name: t('charts-clouds-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'clouds' },
      itemStyle: {
        color: getSubcategoryColor(
          'external_cloud_and_ai',
          'clouds',
          colors.value.lavender.darker,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-ai-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'ai' },
      itemStyle: {
        color: getSubcategoryColor(
          'external_cloud_and_ai',
          'ai',
          colors.value.lavender.dark,
        ),
      },
      label: { show: false },
    },
    // Professional Travel — subcategories: plane, train
    {
      name: t('charts-plane-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'plane' },
      itemStyle: {
        color: getSubcategoryColor(
          'professional_travel',
          'plane',
          colors.value.babyBlue.darker,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-train-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'train' },
      itemStyle: {
        color: getSubcategoryColor(
          'professional_travel',
          'train',
          colors.value.babyBlue.dark,
        ),
      },
      label: { show: false },
    },
    // Research Facilities — subcategories: facilities, it_facilities, animal
    {
      name: t('charts-research-facilities-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'facilities' },
      itemStyle: {
        color: getSubcategoryColor(
          'research_facilities',
          'facilities',
          colors.value.paleYellowGreen.darker,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-research-it-facilities-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'it_facilities' },
      itemStyle: {
        color: getSubcategoryColor(
          'research_facilities',
          'it_facilities',
          colors.value.paleYellowGreen.default,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-research-animal-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'animal' },
      itemStyle: {
        color: getSubcategoryColor(
          'research_facilities',
          'animal',
          colors.value.paleYellowGreen.dark,
        ),
      },
      label: { show: false },
    },

    ...additionalSeriesData.value,
  ];

  return {
    animation: false,
    tooltip: isPrintMode.value
      ? { show: false }
      : {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow',
          },

          formatter: (params: unknown) => {
            const arr = Array.isArray(params) ? params : params ? [params] : [];
            if (!arr.length) {
              emitTooltip(null);
              return '';
            }

            const firstParam = arr[0] as {
              data?: Record<string, unknown>;
              axisValue?: string;
              name?: string;
            };
            const data = firstParam.data;
            const name = firstParam.axisValue || firstParam.name || '';
            const isValidated = validatedLabels.value.has(name);

            if (!isValidated) {
              const moduleName = additionalHeadcountLabels.value.has(name)
                ? t('headcount')
                : additionalBuildingsLabels.value.has(name)
                  ? t('buildings')
                  : name;
              emitTooltip({
                title: name,
                rows: [],
                footer: t('results_validate_module_title', {
                  module: moduleName,
                }),
                tone: 'muted',
              });
              return '';
            }

            const rows: TooltipRow[] = [];
            let total = 0;

            for (const param of [...arr].reverse()) {
              const p = param as {
                seriesName?: string;
                seriesIndex?: number;
                color?: string;
                data?: Record<string, unknown>;
              };
              const series =
                typeof p.seriesIndex === 'number'
                  ? seriesArray[p.seriesIndex]
                  : seriesArray.find((s) => s.name === p.seriesName);
              const key = series?.encode.y;

              if (!data || !key) continue;
              const dataValue = Number(data[key]) || 0;
              if (dataValue > 0) {
                rows.push({
                  label: series?.name ?? p.seriesName ?? '',
                  value: formatTonnesForChart(dataValue),
                  color:
                    (series?.itemStyle?.color as string) ?? p.color ?? '#888',
                });
                total += dataValue;
              }
            }

            if (rows.length === 1) {
              emitTooltip({ rows });
            } else {
              emitTooltip({
                title: name,
                rows,
                separatorRow: {
                  label: t('total'),
                  value: formatTonnesForChart(total),
                },
              });
            }
            return '';
          },
        },

    grid: {
      left: '5%',
      right: '4%',
      top: 80,
      bottom: '0%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      axisLabel: {
        interval: 0,
        rotate: 45,
        fontSize: 9,
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
    yAxis: {
      type: 'value',
      name: t('tco2eq'),
      nameLocation: 'middle',
      nameGap: 40,
      nameRotate: 90,
      nameTextStyle: {
        fontSize: 11,
        fontWeight: 'bold',
      },
      axisLabel: {
        formatter: '{value}',
      },
    },
    graphic: [],
    aria: {
      enabled: true,
      decal: buildChartDecal(colorblindStore.enabled),
    },

    dataset: {
      dimensions: [
        'category',
        'co2',
        'ch4',
        'n2o',
        'refrigerants',
        'process_emissions',
        'lighting',
        'cooling',
        'ventilation',
        'heating_elec',
        'heating_thermal',
        'combustion',
        'scientific',
        'it',
        'other',
        'scientific_equipment',
        'it_equipment',
        'consumable_accessories',
        'biological_chemical_gaseous',
        'services',
        'vehicles',
        'other_purchases',
        'additional',
        'equip_rank1',
        'equip_rank2',
        'equip_rank3',
        'purch_rank1',
        'purch_rank2',
        'purch_rank3',
        'purch_rest',
        'plane',
        'train',
        'clouds',
        'ai',
        'stockage',
        'virtualisation',
        'calcul',
        'ai_provider',
        'facilities',
        'it_facilities',
        'animal',
        'commuting',
        'food',
        'waste',
        'embodied_energy',
      ],
      source: enrichedDatasetSource.value as Array<Record<string, unknown>>,
    },
    series: seriesArray as SeriesOption[],
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
  downloadEchartAsPng(chartRef.value?.chart, 'module-carbon-footprint');

const downloadCSV = () => {
  const escape = (v: unknown) => {
    const s = String(v ?? '');
    return /[,"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };

  // Pivot: one row per category × subcategory pair where the value is non-zero.
  // This avoids the sparse wide-table format where each category gets all
  // possible subcategory columns, 90% of which are empty.
  const SKIP_KEYS = new Set(['category', 'category_key']);

  const rows: Array<[string, string, number]> = datasetSource.value.flatMap(
    (item) => {
      const category = String(item.category ?? '');
      return Object.entries(item)
        .filter(([key, value]) => {
          if (SKIP_KEYS.has(key) || key.startsWith('__')) return false;
          if (typeof value === 'object' && value !== null) return false;
          const n = Number(value);
          // Only emit rows where the subcategory actually has a value
          return Number.isFinite(n) && n !== 0;
        })
        .map(
          ([key, value]) =>
            [category, key, Number(value)] as [string, string, number],
        );
    },
  );

  const headers = [
    t('csv_header_category'),
    t('csv_header_subcategory'),
    t('csv_header_co2'),
  ];
  const csv = [
    headers.map(escape).join(','),
    ...rows.map(([category, subcategory, co2]) =>
      [escape(category), escape(subcategory), escape(co2)].join(','),
    ),
  ].join('\n');

  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = `module-carbon-footprint-${new Date().toISOString().replace(/[:.]/g, '-')}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
};
</script>

<template>
  <q-card
    flat
    class="container container--pa-none full-width module-carbon-chart"
  >
    <q-card-section class="flex justify-between items-center">
      <div class="flex items-center no-wrap">
        <q-icon
          v-if="!isPrintMode"
          name="o_info"
          size="xs"
          color="primary"
          class="cursor-pointer"
          :aria-label="$t('unit_carbon_footprint_scope_tooltip_aria')"
        >
          <q-tooltip
            anchor="center right"
            self="top right"
            class="u-tooltip text-body2"
            max-width="min(92vw, 48rem)"
            :offset="[8, 8]"
          >
            <div class="module-carbon-scope-tooltip">
              <p>
                <strong>{{
                  $t('unit_carbon_footprint_scope_prefix', {
                    scope: $t('charts-scope'),
                    n: 1,
                  })
                }}</strong>
                {{ $t('unit_carbon_footprint_scope_1_desc') }}
              </p>
              <p>
                <strong>{{
                  $t('unit_carbon_footprint_scope_prefix', {
                    scope: $t('charts-scope'),
                    n: 2,
                  })
                }}</strong>
                {{ $t('unit_carbon_footprint_scope_2_desc') }}
              </p>
              <p>
                <strong>{{
                  $t('unit_carbon_footprint_scope_prefix', {
                    scope: $t('charts-scope'),
                    n: 3,
                  })
                }}</strong>
                {{ $t('unit_carbon_footprint_scope_3_desc') }}
              </p>
            </div>
          </q-tooltip>
        </q-icon>
        <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
          {{ props.title ?? $t('unit_carbon_footprint_title') }}
        </span>
      </div>

      <div v-if="!isPrintMode">
        <q-checkbox
          v-if="props.viewAdditionalData === undefined"
          v-model="toggleAdditionalData"
          :label="$t('results_module_carbon_toggle_additional_data')"
          size="xs"
          color="accent"
        />
      </div>
    </q-card-section>

    <q-card-section
      class="chart-container flex justify-center items-center module-carbon-chart__body"
    >
      <v-chart
        ref="chartRef"
        :key="colorblindStore.enabled ? 'cb' : 'default'"
        :class="['chart', { 'chart--print': isPrintMode }]"
        autoresize
        :option="chartOption"
        @rendered="recalculateScopeRects"
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
    <q-separator v-if="!isPrintMode" />
    <q-card-section v-if="!isPrintMode" class="flex justify-start q-gutter-sm">
      <q-btn
        unelevated
        no-caps
        outline
        icon="o_download"
        :label="$t('common_download_as_png')"
        size="xs"
        dense
        class="text-weight-bold q-px-sm"
        @click="downloadPNG"
      />
      <q-btn
        unelevated
        no-caps
        outline
        icon="o_download"
        :label="$t('common_download_as_csv')"
        size="xs"
        dense
        class="text-weight-bold q-px-sm"
        @click="downloadCSV"
      />
    </q-card-section>
  </q-card>
</template>

<style scoped>
.module-carbon-chart {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.module-carbon-chart__body {
  flex: 1;
}

.chart {
  width: 100%;
  min-height: 420px;
}

.chart--print {
  min-height: 320px;
}

@media (max-width: 1320px) {
  .chart:not(.chart--print) {
    width: 100%;
  }
}
</style>

<!-- Tooltip content is rendered in a portal; i18n supplies .module-carbon-scope-tooltip -->
<style lang="scss">
.module-carbon-scope-tooltip {
  min-width: 36rem;
}

.module-carbon-scope-tooltip p {
  margin: 0 0 0.5rem;
  line-height: 1.45;
  white-space: normal;
}

.module-carbon-scope-tooltip p:last-child {
  margin-bottom: 0;
}
</style>
