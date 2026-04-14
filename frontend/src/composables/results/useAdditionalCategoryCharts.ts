import type { EChartsOption } from 'echarts';
import {
  CHART_SUBCATEGORY_COLOR_SCHEMES,
  getChartSubcategoryColor,
} from 'src/constant/charts';

export type AdditionalCategoryKey =
  | 'commuting'
  | 'food'
  | 'waste'
  | 'embodied_energy';

export type DisplayEntry = {
  key: string;
  value: number;
  quantity: number;
  quantity_unit: string;
};

type LabelFns = {
  t: (key: string, params?: Record<string, unknown>) => string;
  te: (key: string) => boolean;
};

function subcategoryLabel({ t, te }: LabelFns, key: string): string {
  const i18nKey = `charts-${key.replace(/_/g, '-')}-subcategory`;
  return te(i18nKey) ? t(i18nKey) : key;
}

export function buildDoughnutOption(
  labels: LabelFns,
  category: AdditionalCategoryKey,
  entries: DisplayEntry[],
  useQuantity: boolean,
): EChartsOption {
  const colorScheme = CHART_SUBCATEGORY_COLOR_SCHEMES.value[category] ?? {};
  const noBreakdownColor = '#D5D5D5';
  const hasBreakdown = entries.length > 1;

  const data = entries
    .filter((e) => (useQuantity ? e.quantity > 0 : e.value > 0))
    .map((e) => ({
      name: subcategoryLabel(labels, e.key),
      value: useQuantity ? e.quantity : e.value,
      itemStyle: {
        color: hasBreakdown
          ? (colorScheme[e.key] ?? '#CFD4EE')
          : noBreakdownColor,
        borderColor: '#ffffff',
        borderWidth: 1,
      },
    }));

  if (data.length === 0) {
    return {
      animation: false,
      tooltip: { show: false },
      legend: { show: false },
      series: [],
      graphic: [
        {
          type: 'text',
          left: 'center',
          top: 'middle',
          style: {
            text: labels.t('no-chart-data'),
            fill: '#7A7A7A',
            fontSize: 14,
            fontWeight: 500,
          },
        },
      ],
    };
  }

  return {
    animation: false,
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      extraCssText: 'z-index: 9999;',
      formatter: (params: unknown) => {
        const p = params as { name?: unknown; percent?: unknown };
        const name = String(p.name ?? '');
        const percent =
          typeof p.percent === 'number' ? p.percent : Number(p.percent);
        const percentDisplay = Number.isFinite(percent) ? percent : 0;
        const percentText = Number.isFinite(percentDisplay)
          ? percentDisplay.toFixed(0)
          : '0';
        return `${name}: ${percentText}%`;
      },
    },
    legend: { show: false },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        animation: false,
        avoidLabelOverlap: false,
        label: { show: false },
        emphasis: { label: { show: false } },
        data,
      },
    ],
  };
}

export function legendItems(
  labels: LabelFns,
  category: AdditionalCategoryKey,
  keys: string[],
): { key: string; label: string; color: string }[] {
  const hasBreakdown = keys.length > 1;
  return keys.map((key) => ({
    key,
    label: subcategoryLabel(labels, key),
    color: hasBreakdown
      ? getChartSubcategoryColor(category, key, '#CFD4EE')
      : '#D5D5D5',
  }));
}

export const WASTE_DISPLAY_CATEGORY: Record<string, string> = {
  incineration: 'domestic',
  composting: 'organic',
  organic_waste_food_leftovers: 'organic',
  cooking_vegetable_oil: 'organic',
  paper: 'paper',
  cardboard: 'paper',
  plastics: 'plastic',
  glass: 'glass',
  ferrous_metals: 'metals',
  non_ferrous_metals: 'metals',
  electronics: 'electronics',
  wood: 'wood',
  pet: 'plastic',
  aluminum: 'metals',
  textile: 'other',
  toner_and_ink_cartridges: 'other',
  inert_waste: 'other',
};

export const WASTE_DISPLAY_ORDER = [
  'domestic',
  'organic',
  'paper',
  'plastic',
  'glass',
  'metals',
  'electronics',
  'wood',
  'other',
];
