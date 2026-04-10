<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import { graphic } from 'echarts';
import { colors, getChartSubcategoryColor } from 'src/constant/charts';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
]);

import type { EmissionBreakdownResponse } from 'src/stores/modules';
import { formatTonnesForChart } from 'src/utils/number';

const props = defineProps<{
  breakdownData?: EmissionBreakdownResponse | null;
  title?: string;
}>();

const { t } = useI18n();
const toggleAdditionalData = ref(false);

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
  buildings_room: 1,
  buildings_energy_combustion: 2,
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
} | null = null;

function recalculateScopeRects() {
  const chart = chartRef.value?.chart;
  if (!chart) return;

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
  const showAdditional = toggleAdditionalData.value && dividerX !== null;

  // Check if state has changed
  const newState = {
    s1Left: s1?.left,
    s2Left: s2?.left,
    s3Left: s3?.left,
    dividerX,
    showAdditional,
  };
  if (
    lastScopeState?.s1Left === newState.s1Left &&
    lastScopeState?.s2Left === newState.s2Left &&
    lastScopeState?.s3Left === newState.s3Left &&
    lastScopeState?.dividerX === newState.dividerX &&
    lastScopeState?.showAdditional === newState.showAdditional
  ) {
    return; // nothing changed — stop the loop
  }
  lastScopeState = newState;

  const elements: object[] = [
    ...(s1
      ? [
          {
            type: 'rect',
            id: 'sr1',
            left: s1.left,
            top: '15px',
            shape: { width: s1.width, height: 300 },
            style: {
              fill: new graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(248,248,248,0.9)' },
                { offset: 1, color: 'rgba(248,248,248,0.1)' },
              ]),
            },
            silent: true,
          },
          {
            type: 'text',
            id: 'st1',
            left: s1.left + 10,
            top: '30px',
            style: {
              fill: '#000000',
              text: t('charts-scope') + ' 1',
              font: '11px SuisseIntl',
            },
            silent: true,
          },
        ]
      : []),
    ...(s2
      ? [
          {
            type: 'rect',
            id: 'sr2',
            left: s2.left,
            top: '15px',
            shape: { width: s2.width, height: 300 },
            style: {
              fill: new graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(240,240,240,0.9)' },
                { offset: 1, color: 'rgba(240,240,240,0.1)' },
              ]),
            },
            silent: true,
          },
          {
            type: 'text',
            id: 'st2',
            left: s2.left + 10,
            top: '30px',
            style: {
              fill: '#000000',
              text: t('charts-scope') + ' 2',
              font: '11px SuisseIntl',
            },
            silent: true,
          },
        ]
      : []),
    ...(s3
      ? [
          {
            type: 'rect',
            id: 'sr3',
            left: s3.left,
            top: '15px',
            shape: { width: s3.width, height: 300 },
            style: {
              fill: new graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(229,229,229,0.9)' },
                { offset: 1, color: 'rgba(229,229,229,0.1)' },
              ]),
            },
            silent: true,
          },
          {
            type: 'text',
            id: 'st3',
            left: s3.left + 10,
            top: '30px',
            style: {
              fill: '#000000',
              text: t('charts-scope') + ' 3',
              font: '11px SuisseIntl',
            },
            silent: true,
          },
        ]
      : []),
    {
      type: 'text',
      id: 'smain',
      left: s1 ? s1.left + 10 : 56,
      top: '0px',
      style: {
        fill: '#000000',
        text: t('charts-main-category'),
        font: '11px SuisseIntl',
      },
      silent: true,
    },
    ...(showAdditional
      ? [
          {
            type: 'rect',
            id: 'sadd',
            left: dividerX,
            top: '15px',
            shape: { width: additionalRect?.width ?? 200, height: 300 },
            style: {
              fill: new graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(215,215,215,0.9)' },
                { offset: 1, color: 'rgba(215,215,215,0.1)' },
              ]),
            },
            silent: true,
          },
          {
            type: 'text',
            id: 'stadd',
            left: dividerX + 10,
            top: '0px',
            style: {
              fill: '#000000',
              text: t('charts-additional-category'),
              font: '11px SuisseIntl',
            },
            silent: true,
          },
          {
            type: 'rect',
            id: 'sdiv',
            left: dividerX,
            top: '0px',
            shape: { width: 1, height: 420 },
            style: {
              fill: new graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(0,0,0,1)' },
                { offset: 1, color: 'rgba(240,240,240,0.1)' },
              ]),
            },
            z: 100,
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
          {
            type: 'rect',
            id: 'sdiv',
            left: 0,
            top: 0,
            shape: { width: 0, height: 0 },
            style: { opacity: 0 },
            silent: true,
          },
        ]),
  ];

  requestAnimationFrame(() => {
    chart.setOption({ graphic: elements }, {
      replaceMerge: ['graphic'],
    } as Parameters<typeof chart.setOption>[1]);
  });
}

const CATEGORY_LABEL_MAP: Record<string, string> = {
  commuting: 'charts-commuting-category', // Headcount
  food: 'charts-food-category',
  waste: 'charts-waste-category',
  process_emissions: 'charts-process-emissions-category',
  buildings_room: 'charts-buildings-room-category',
  buildings_energy_combustion: 'charts-buildings-energy-combustion-category',
  embodied_energy: 'charts-embodied-energy-category',
  equipment: 'equipment-electric-consumption',
  external_cloud_and_ai: 'external-cloud-and-ai',
  purchases: 'purchase',
  professional_travel: 'professional-travel',
  research_facilities: 'charts-research-facilities-category',
};

function translateCategory(
  entry: Record<string, unknown>,
): Record<string, unknown> {
  const cat = entry.category as string;
  const i18nKey = CATEGORY_LABEL_MAP[cat];
  return { ...entry, category: i18nKey ? t(i18nKey) : cat };
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

// Keys not translated here — moved to computed properties below
const ADDITIONAL_CATEGORY_KEY_IDS = [
  'charts-commuting-category',
  'charts-food-category',
  'charts-waste-category',
  'charts-embodied-energy-category',
];

const MAIN_CATEGORY_ORDER_IDS = [
  'charts-process-emissions-category',
  'charts-buildings-room-category',
  'charts-buildings-energy-combustion-category',
  'equipment-electric-consumption',
  'external-cloud-and-ai',
  'purchase',
  'professional-travel',
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
      .map(translateCategory),
  );

  let allData = baseData;
  if (toggleAdditionalData.value) {
    const additionalData = collapseByCategory(
      props.breakdownData.additional_breakdown
        .map((entry) => {
          const category = String(entry.category ?? '');
          return isCategoryValidated(category)
            ? entry
            : zeroNumericValues(entry);
        })
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

const additionalSeriesData = computed(() => {
  if (!toggleAdditionalData.value) return [];

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
      name: 'CO₂',
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
      name: 'CH4',
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
      name: 'N2O',
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
      name: 'Refrigerants',
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
    // Equipment — subcategories: scientific, it, other
    {
      name: t('charts-scientific-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'scientific' },
      itemStyle: {
        color: getSubcategoryColor(
          'equipment',
          'scientific',
          colors.value.mauve.darker,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-equipment-it'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'it' },
      itemStyle: {
        color: getSubcategoryColor('equipment', 'it', colors.value.mauve.dark),
      },
      label: { show: false },
    },
    {
      name: t('charts-other-purchases-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'other' },
      itemStyle: {
        color: getSubcategoryColor(
          'equipment',
          'other',
          colors.value.mauve.default,
        ),
      },
      label: { show: false },
    },
    // Purchases — YY subcategories
    {
      name: t('charts-scientific-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'scientific_equipment' },
      itemStyle: {
        color: getSubcategoryColor(
          'purchases',
          'scientific_equipment',
          colors.value.lavender.darker,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-equipment-it'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'it_equipment' },
      itemStyle: {
        color: getSubcategoryColor(
          'purchases',
          'it_equipment',
          colors.value.lavender.dark,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-consumables-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'consumable_accessories' },
      itemStyle: {
        color: getSubcategoryColor(
          'purchases',
          'consumable_accessories',
          colors.value.lavender.default,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-bio-chemicals-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'biological_chemical_gaseous' },
      itemStyle: {
        color: getSubcategoryColor(
          'purchases',
          'biological_chemical_gaseous',
          colors.value.lavender.light,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-services-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'services' },
      itemStyle: {
        color: getSubcategoryColor(
          'purchases',
          'services',
          colors.value.lavender.lighter,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-other-purchases-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'vehicles' },
      itemStyle: {
        color: getSubcategoryColor(
          'purchases',
          'vehicles',
          colors.value.lavender.default,
        ),
      },
      label: { show: false },
    },
    {
      name: t('charts-other-purchases-subcategory'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: { x: 'category', y: 'additional' },
      itemStyle: {
        color: getSubcategoryColor(
          'purchases',
          'additional',
          colors.value.lavender.light,
        ),
      },
      label: { show: false },
    },
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
          colors.value.paleYellowGreen.darker,
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
          colors.value.paleYellowGreen.dark,
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
    // Research Facilities — subcategories: facilities, animal
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
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },

      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : params ? [params] : [];
        if (!arr.length) return '';
        const p = arr[0] as {
          data?: Record<string, unknown>;
          axisValue?: string;
          name?: string;
          seriesName?: string;
          marker?: string;
          value?: number | number[];
        };
        const data = p.data;
        const name = p.axisValue || p.name || '';
        const isValidated = validatedLabels.value.has(name);

        if (!isValidated) {
          const moduleName = additionalHeadcountLabels.value.has(name)
            ? t('headcount')
            : additionalBuildingsLabels.value.has(name)
              ? t('buildings')
              : name;
          return `<strong>${name}</strong><br/><span style="color:#aaa">${t('results_validate_module_title', { module: moduleName })}</span>`;
        }

        let total = 0;
        let tooltip = `<strong>${name}</strong><br/>`;

        arr.reverse().forEach((param: unknown) => {
          const p = param as {
            seriesName?: string;
            seriesIndex?: number;
            marker?: string;
            value?: number | number[];
            data?: Record<string, unknown>;
          };
          const series =
            typeof p.seriesIndex === 'number'
              ? seriesArray[p.seriesIndex]
              : seriesArray.find((s) => s.name === p.seriesName);
          const key = series?.encode.y;

          if (!data || !key) return;
          const dataValue = Number(data[key]) || 0;
          if (dataValue > 0) {
            tooltip += `${p.marker || ''} ${series?.name || p.seriesName || ''}: <strong>${formatTonnesForChart(dataValue)} </strong><br/>`;
            total += dataValue;
          }
        });

        const totalDisplay = formatTonnesForChart(total);

        return `${tooltip}<hr style="margin: 4px 0"/>Total: <strong>${totalDisplay}</strong>`;
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
        'additional',
        'plane',
        'train',
        'clouds',
        'ai',
        'stockage',
        'virtualisation',
        'calcul',
        'ai_provider',
        'facilities',
        'animal',
        'commuting',
        'food',
        'waste',
        'embodied_energy',
      ],
      source: datasetSource.value as Array<Record<string, unknown>>,
    },
    series: seriesArray as echarts.SeriesOption[],
  };
});

const chartRef = ref<InstanceType<typeof VChart>>();

const downloadPNG = async () => {
  const chart = chartRef.value?.chart;
  if (!chart) return;

  try {
    // Wait a bit to ensure no animation in the image
    await new Promise((resolve) => setTimeout(resolve, 200));

    const url = chart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff',
    });

    const link = document.createElement('a');
    link.href = url;
    link.download = `module-carbon-footprint-${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } catch (error) {
    console.error('Error downloading chart:', error);
  }
};

const downloadCSV = () => {
  const escape = (v: unknown) => {
    const s = String(v ?? '');
    return /[,"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };

  const headers = [
    ...new Set(
      datasetSource.value.flatMap((item) =>
        Object.entries(item)
          .filter(([key, value]) => {
            if (key.startsWith('__')) return false;
            if (typeof value === 'object' && value !== null) return false;
            return true;
          })
          .map(([key]) => key),
      ),
    ),
  ].sort((a, b) =>
    a === 'category' ? -1 : b === 'category' ? 1 : a.localeCompare(b),
  );

  const csv = [
    headers.map(escape).join(','),
    ...datasetSource.value.map((item) =>
      headers.map((key) => escape(item[key])).join(','),
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

      <q-checkbox
        v-model="toggleAdditionalData"
        :label="$t('results_module_carbon_toggle_additional_data')"
        size="xs"
        color="accent"
      />
    </q-card-section>

    <q-card-section
      class="chart-container flex justify-center items-center module-carbon-chart__body"
    >
      <v-chart
        ref="chartRef"
        class="chart"
        autoresize
        :option="chartOption"
        @rendered="recalculateScopeRects"
      />
    </q-card-section>

    <q-card-actions align="center" class="q-px-md q-pb-md q-pt-none">
      <q-btn
        unelevated
        no-caps
        outline
        icon="o_download"
        :label="$t('common_download_as_png')"
        size="sm"
        class="text-weight-medium q-mr-xs"
        @click="downloadPNG"
      />
      <q-btn
        unelevated
        no-caps
        outline
        icon="o_download"
        :label="$t('common_download_as_csv')"
        size="sm"
        class="text-weight-medium"
        @click="downloadCSV"
      />
    </q-card-actions>
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
  min-height: 500px;
}

@media (max-width: 1320px) {
  .chart {
    width: 95%;
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
