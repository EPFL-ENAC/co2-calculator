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

const scopeConfig = computed(() => {
  if (toggleAdditionalData.value) {
    return {
      scope1RectWidth: 72,
      scope2RectLeft: 118,
      scope2RectWidth: 72,
      scope3RectLeft: 190,
      scope3RectWidth: 144,
      estimatedRectLeft: 334,
      estimatedText: t('charts-additional-category'),
    };
  }

  return {
    scope1RectWidth: 108,
    scope2RectLeft: 154,
    scope2RectWidth: 108,
    scope3RectLeft: 262,
    scope3RectWidth: 330,
    estimatedRectLeft: 0,
    estimatedText: '',
  };
});

const CATEGORY_LABEL_MAP: Record<string, string> = {
  process_emissions: 'charts-process-emissions-category',
  buildings_room: 'charts-buildings-room-category',
  buildings_energy_combustion: 'charts-buildings-energy-combustion-category',
  equipment: 'equipment-electric-consumption',
  external_cloud_and_ai: 'external-cloud-and-ai',
  purchases: 'purchase',
  research_facilities: 'charts-research-facilities-category',
  professional_travel: 'professional-travel',
  commuting: 'charts-commuting-category',
  food: 'charts-food-category',
  waste: 'charts-waste-category',
  grey_energy: 'charts-grey-energy-category',
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
    return [...baseData, ...additionalData];
  }
  return baseData;
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
      name: t('charts-grey-energy-category'),
      type: 'bar' as const,
      stack: 'total',
      animation: true,
      encode: {
        x: 'category',
        y: 'grey_energy',
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

const ADDITIONAL_CATEGORIES = ['commuting', 'food', 'waste', 'grey_energy'];

const additionalLabels = computed(
  () =>
    new Set(
      ADDITIONAL_CATEGORIES.map((cat) => {
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
      name: 'CO2',
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
          const moduleName = additionalLabels.value.has(name)
            ? t('headcount')
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
    graphic: [
      // Scope 1 overlay (Processes, Buildings energy consumption)
      {
        type: 'rect',
        left: '46px',
        top: '15px',
        shape: {
          width: scopeConfig.value.scope1RectWidth,
          height: 300,
        },
        style: {
          fill: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(248,248,248,0.9)' },
            { offset: 1, color: 'rgba(248,248,248,0.1)' },
          ]),
        },
      },
      {
        type: 'text',
        left: '56px',
        top: '30px',
        style: {
          fill: '#000000',
          text: t('charts-scope') + ' 1',
          font: '11px SuisseIntl',
        },
      },
      // Scope 2 overlay (Energy combustion, Equipment)
      {
        type: 'rect',
        left: scopeConfig.value.scope2RectLeft,
        top: '15px',
        shape: {
          width: scopeConfig.value.scope2RectWidth,
          height: 300,
        },
        style: {
          fill: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(240,240,240,0.9)' },
            { offset: 1, color: 'rgba(240,240,240,0.1)' },
          ]),
        },
      },
      {
        type: 'text',
        left: scopeConfig.value.scope2RectLeft + 10,
        top: '30px',
        style: {
          fill: '#000000',
          text: t('charts-scope') + ' 2',
          font: '11px SuisseIntl',
        },
      },
      // Scope 3 overlay (External cloud & AI, Purchases, Research facilities, Professional travel)
      {
        type: 'rect',
        left: scopeConfig.value.scope3RectLeft,
        top: '15px',
        shape: {
          width: scopeConfig.value.scope3RectWidth,
          height: 300,
        },
        style: {
          fill: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(229,229,229,0.9)' },
            { offset: 1, color: 'rgba(229,229,229,0.1)' },
          ]),
        },
      },
      {
        type: 'text',
        left: scopeConfig.value.scope3RectLeft + 10,
        top: '30px',
        style: {
          fill: '#000000',
          text: t('charts-scope') + ' 3',
          font: '11px SuisseIntl',
        },
      },
      {
        type: 'text',
        left: '56px',
        top: '00px',
        style: {
          fill: '#000000',
          text: t('charts-main-category'),
          font: '11px SuisseIntl',
        },
      },
      ...(() => {
        if (toggleAdditionalData.value) {
          return [
            // Additional categories background (darker grey)
            {
              type: 'rect',
              left: scopeConfig.value.estimatedRectLeft,
              top: '15px',
              shape: {
                width: 200,
                height: 300,
              },
              style: {
                fill: new graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: 'rgba(215,215,215,0.9)' },
                  { offset: 1, color: 'rgba(215,215,215,0.1)' },
                ]),
              },
            },
            {
              type: 'text',
              left: scopeConfig.value.estimatedRectLeft + 10,
              top: '0px',
              style: {
                fill: '#000000',
                text: scopeConfig.value.estimatedText,
                font: '11px SuisseIntl',
              },
            },
            // Divider line
            {
              type: 'rect',
              left: scopeConfig.value.estimatedRectLeft,
              top: '0px',
              shape: {
                width: 1,
                height: 420,
              },
              style: {
                fill: new graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: 'rgba(0,0,0)' },
                  { offset: 1, color: 'rgba(240,240,240,0.1)' },
                ]),
              },
              z: 100,
            },
          ];
        }
        return [];
      })(),
    ],
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
        'commuting',
        'food',
        'waste',
        'grey_energy',
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
  <q-card flat class="container container--pa-none">
    <q-card-section class="flex justify-between items-center">
      <div>
        <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
          {{ props.title ?? $t('unit_carbon_footprint_title') }}
        </span>
      </div>

      <div>
        <q-btn
          unelevated
          no-caps
          outline
          icon="o_download"
          :label="$t('common_download_as_png')"
          size="sm"
          class="text-weight-medium q-mr-sm"
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
      </div>
      <q-checkbox
        v-model="toggleAdditionalData"
        :label="$t('results_module_carbon_toggle_additional_data')"
        size="xs"
        color="accent"
      />
    </q-card-section>
    <q-card-section class="chart-container flex justify-center items-center">
      <v-chart ref="chartRef" class="chart" autoresize :option="chartOption" />
    </q-card-section>
  </q-card>
</template>

<style scoped>
.chart {
  width: 500px;
  min-height: 500px;
}
</style>
