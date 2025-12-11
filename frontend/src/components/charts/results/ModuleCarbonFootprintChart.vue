<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import * as echarts from 'echarts';
import type { EChartsOption, BarSeriesOption } from 'echarts';
import { getElement, colorblindMode } from 'src/constant/charts';

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
let resizeHandler: (() => void) | null = null;
const { t, locale } = useI18n();

interface CategoryConfig {
  elementId: string;
  subCategories?: string[];
  value?: number;
  values?: Record<string, number>;
}

// Category configurations
const categories: CategoryConfig[] = [
  { elementId: 'charts-unit-gas-category', value: 2.5 },
  {
    elementId: 'charts-infrastructure-gas-category',
    value: 2.0,
  },
  {
    elementId: 'charts-infrastructure-category',
    values: {
      'charts-heating-subcategory': 9.0,
      'charts-cooling-subcategory': 3.0,
      'charts-ventilation-subcategory': 9.0,
      'charts-lighting-subcategory': 3.0,
    },
  },
  {
    elementId: 'charts-equipment-category',
    values: {
      'charts-scientific-subcategory': 10.0,
      'charts-it-subcategory': 3.0,
    },
  },
  { elementId: 'charts-commuting-category', value: 8.0 },
  { elementId: 'charts-food-category', value: 2.5 },
  {
    elementId: 'charts-professional-travel-category',
    values: {
      'charts-train-subcategory': 1.5,
      'charts-plane-subcategory': 3.0,
    },
  },
  { elementId: 'charts-it-category', value: 25.0 },
  {
    elementId: 'charts-research-core-facilities-category',
    values: { SCITAS: 1.0, RCP: 1.5 },
  },
  {
    elementId: 'charts-purchases-category',
    values: {
      'charts-bio-chemicals-subcategory': 2.0,
      'charts-consumables-subcategory': 3.0,
      'charts-equipment-subcategory': 1.0,
      'charts-services-subcategory': 2.0,
      'charts-other-purchases-subcategory': 0.2,
    },
  },
  { elementId: 'charts-waste-category', value: 10.0 },
  {
    elementId: 'charts-grey-energy-category',
    values: { GC: 4.0, PH: 4.0 },
  },
];

const initChart = () => {
  if (!chartRef.value) return;

  // Dispose existing chart instance if it exists
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }

  // Remove existing resize listener if it exists
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler);
    resizeHandler = null;
  }

  chartInstance = echarts.init(chartRef.value);

  const barLabels = categories.map((c) => t(c.elementId));

  // Build all mappings and dataset in one pass
  const translatedNameToelementId: Record<string, string> = {};
  const barToSubCategories: Record<string, string[]> = {};
  const subCategoryToMainCategory: Record<string, string> = {};
  const datasetSource: Record<string, string | number>[] = [];

  categories.forEach((config) => {
    const categoryName = t(config.elementId);
    translatedNameToelementId[categoryName] = config.elementId;

    const subCats = config.subCategories?.length
      ? config.subCategories
      : config.values
        ? Object.keys(config.values)
        : [categoryName];

    barToSubCategories[config.elementId] = subCats;
    subCats.forEach((sub) => {
      subCategoryToMainCategory[sub] = config.elementId;
    });

    datasetSource.push({
      bar: categoryName,
      ...(config.value !== undefined
        ? { [categoryName]: config.value }
        : config.values || {}),
    });
  });

  const subCategories = Object.keys(subCategoryToMainCategory);

  const dataset = {
    dimensions: ['bar', ...subCategories],
    source: datasetSource,
  };

  // Color helpers
  const getColor = (elementId: string, shade: number = 2): string =>
    getElement(elementId, shade);

  const getSubCategoryColor = (subCategory: string, index: number): string => {
    const mainCategory = subCategoryToMainCategory[subCategory] || subCategory;
    const categoryConfig = categories.find((c) => c.elementId === mainCategory);
    // If category has a single value (no subcategories), use middle shade (2)
    const shade = categoryConfig?.value !== undefined ? 2 : Math.min(index, 4);
    return getColor(mainCategory, shade);
  };

  // Top-level category labels (re-evaluated on each init to reflect locale changes)
  const topLevelCategories = [
    { label: t('charts-calculated'), startIndex: 0, endIndex: 7 },
    { label: t('charts-estimated'), startIndex: 8, endIndex: 11 },
  ];

  // Scope configurations (re-evaluated on each init to reflect locale changes)
  const scopeAreas = [
    {
      label: t('charts-scope') + ' 1',
      color: '#F5F5F5',
      startIndex: 0,
      endIndex: 1,
    },
    {
      label: t('charts-scope') + ' 2',
      color: '#E8E8E8',
      startIndex: 2,
      endIndex: 3,
    },
    {
      label: t('charts-scope') + ' 3',
      color: '#D0D0D0',
      startIndex: 4,
      endIndex: 7,
    },
    { label: '', color: '#D0D0D0', startIndex: 8, endIndex: 11 },
  ];

  // Calculate max value for y-axis
  const calculateMaxValue = (): number =>
    Math.max(
      ...dataset.source.map((row) =>
        subCategories.reduce(
          (sum, sub) => sum + ((row[sub] as number) || 0),
          0,
        ),
      ),
    ) + 10;

  // Get subcategories with data
  const subCategoriesWithData = subCategories.filter((sub) =>
    dataset.source.some((row) => {
      const val = row[sub];
      return val !== null && val !== undefined && val !== 0;
    }),
  );

  // Sort subcategories for proper stacking
  const sortedSubCategories = [...subCategoriesWithData].sort((a, b) => {
    const mainA = subCategoryToMainCategory[a] || a;
    const mainB = subCategoryToMainCategory[b] || b;
    if (mainA !== mainB) return 0;
    const subCats = barToSubCategories[mainA] || [];
    return subCats.indexOf(a) - subCats.indexOf(b);
  });

  // Create bar series
  const categorySeries: BarSeriesOption[] = sortedSubCategories.map(
    (subCategory) => {
      const mainCategory =
        subCategoryToMainCategory[subCategory] || subCategory;
      const subCats = barToSubCategories[mainCategory] || [];
      const index = subCats.indexOf(subCategory);
      // Only translate if it's a translation key (starts with 'charts-'), otherwise use as-is (building names)
      const displayName = subCategory.startsWith('charts-')
        ? t(subCategory)
        : subCategory;
      return {
        name: displayName,
        type: 'bar',
        datasetIndex: 0,
        encode: { y: subCategory },
        stack: 'total',
        barWidth: '80%',
        barCategoryGap: '20%',

        itemStyle: {
          color: getSubCategoryColor(subCategory, index >= 0 ? index : 0),
        },
        emphasis: {
          itemStyle: {
            color: getSubCategoryColor(subCategory, index >= 0 ? index : 0),
          },
        },
        animation: true,
        animationDuration: 300,
        animationEasing: 'cubicOut',
        legendHoverLink: false,
      };
    },
  );

  // Create legend series
  const legendSeries: BarSeriesOption[] = categories.map((config) => ({
    name: t(config.elementId),
    type: 'bar',
    data: [],
    itemStyle: { color: getColor(config.elementId) },
  }));

  const option: EChartsOption = {
    dataset: [dataset],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'none' },
      confine: true,
      extraCssText: 'min-width: 220px;',
      formatter: (params: unknown) => {
        if (!Array.isArray(params) || params.length === 0) return '';
        const first = params[0] as { axisValue?: string; seriesName?: string };
        if (!first?.axisValue) return '';

        const categoryName = first.axisValue;
        const categoryRow = dataset.source.find(
          (row) => row.bar === categoryName,
        );
        if (!categoryRow) return '';

        // Get elementId from translated name
        const elementId = translatedNameToelementId[categoryName];
        if (!elementId) return '';

        const subCats = barToSubCategories[elementId];
        const subCategoryData = [];

        let categoryTotal = 0;

        subCats.forEach((subCat) => {
          const value = categoryRow[subCat];

          const mainCategoryelementId =
            subCategoryToMainCategory[subCat] || elementId;
          const subCatsForCategory =
            barToSubCategories[mainCategoryelementId] || [];
          const index = subCatsForCategory.indexOf(subCat);
          const color = getSubCategoryColor(subCat, index >= 0 ? index : 0);

          subCategoryData.push({
            name: subCat,
            value,
            color,
          });
          categoryTotal += Number(value);
        });

        if (subCategoryData.length === 0) return '';

        // If single subcategory, show dot at category level
        if (subCategoryData.length === 1) {
          const item = subCategoryData[0];
          return `<div style="display: flex; justify-content: space-between; align-items: center;"><span><span style="color: ${item.color}">●</span> <b>${categoryName}</b></span> <b>${categoryTotal.toFixed(1)}</b></div>`;
        }

        // Category name with total and all subcategories
        let result = `<div style="display: flex; justify-content: space-between; align-items: center;"><b>${categoryName}</b> <b>${categoryTotal.toFixed(1)}</b></div>`;
        result += '<br/>';
        [...subCategoryData].reverse().forEach((item) => {
          // Only translate if it's a translation key (starts with 'charts-'), otherwise use as-is (building names)
          const displayName = item.name.startsWith('charts-')
            ? t(item.name)
            : item.name;
          result += `<div style="display: flex; justify-content: space-between; align-items: center;"><span><span style="color: ${item.color}">●</span> <span>${displayName}</span></span> <span>${item.value.toFixed(1)}</span></div>`;
        });

        return result;
      },
    },
    legend: {
      data: barLabels,
      bottom: 0,
      type: 'plain',
      orient: 'horizontal',
      itemGap: 8,
      itemWidth: 10,
      itemHeight: 10,
      selectedMode: false,
    },
    grid: {
      left: '5%',
      right: '0%',
      bottom: '15%',
      top: '0%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: barLabels,
      axisLabel: { show: false },
      boundaryGap: true,
    },
    yAxis: {
      type: 'value',
      name: 't CO₂-eq',
      nameLocation: 'middle',
      nameGap: 30,
      nameRotate: 90,
      nameTextStyle: { fontSize: 10, fontWeight: 'normal' },
      max: calculateMaxValue(),
      splitLine: { show: true, lineStyle: { color: '#E0E0E0', type: 'solid' } },
    },
    series: [...legendSeries, ...categorySeries],
  };

  chartInstance.setOption(option);

  // Add scope rectangles and separator line using graphics (calculated after render)
  const updateScopeGraphics = () => {
    if (!chartInstance) return;

    // Get plot area bounds from option
    const option = chartInstance.getOption() as EChartsOption;
    const grid =
      (Array.isArray(option.grid) ? option.grid[0] : option.grid) || {};
    const gridTop = parseFloat(String(grid.top || '0%').replace('%', '')) || 0;
    const gridBottom =
      parseFloat(String(grid.bottom || '15%').replace('%', '')) || 15;
    const chartHeight = chartInstance.getHeight();
    const plotTop = (chartHeight * gridTop) / 100;
    const plotBottom = chartHeight - (chartHeight * gridBottom) / 100;
    const plotHeight = plotBottom - plotTop;

    // Calculate bar width from spacing between first two categories
    const firstPos = chartInstance.convertToPixel('xAxis', barLabels[0]);
    const secondPos = chartInstance.convertToPixel('xAxis', barLabels[1]);
    const barWidth = firstPos && secondPos ? Math.abs(secondPos - firstPos) : 0;

    // Build top-level category labels (Calculated, Estimated)
    const topLevelGraphics = topLevelCategories.map((category) => {
      const startPos = chartInstance!.convertToPixel(
        'xAxis',
        barLabels[category.startIndex],
      );
      const endPos = chartInstance!.convertToPixel(
        'xAxis',
        barLabels[category.endIndex],
      );

      const startX = startPos - barWidth / 2;
      const endX = endPos + barWidth / 2;
      const width = endX - startX;

      return {
        type: 'text' as const,
        x: startX + width / 2,
        y: plotTop + 10,
        style: {
          text: category.label,
          fontSize: 11,
          fontWeight: 'bold',
          textAlign: 'center',
        },
        z: 3,
      };
    });

    // Build scope graphics array
    const scopeGraphics = scopeAreas
      .map((scope) => {
        const startPos = chartInstance!.convertToPixel(
          'xAxis',
          barLabels[scope.startIndex],
        );
        const endPos = chartInstance!.convertToPixel(
          'xAxis',
          barLabels[scope.endIndex],
        );

        const startX = startPos - barWidth / 2;
        const endX = endPos + barWidth / 2;
        const width = endX - startX;

        return [
          // Rectangle
          {
            type: 'rect' as const,
            shape: {
              x: startX,
              y: plotTop,
              width: width,
              height: plotHeight,
            },
            style: {
              fill: scope.color,
              opacity: 0.3,
            },
            z: 0,
          },
          {
            type: 'text' as const,
            x: startX + width / 2,
            y: plotTop + 30,
            style: {
              text: scope.label,
              fontSize: 10,
              fontWeight: 'bold',
              textAlign: 'center',
            },
            z: 1,
          },
        ];
      })
      .flat();

    // Add separator line after Scope 3 (between index 7 and 8)
    const separatorPos = chartInstance.convertToPixel('xAxis', barLabels[7]);
    const nextPos = chartInstance.convertToPixel('xAxis', barLabels[8]);
    const separatorGraphics =
      separatorPos && nextPos
        ? [
            {
              type: 'line' as const,
              shape: {
                x1: (separatorPos + nextPos) / 2,
                y1: plotTop,
                x2: (separatorPos + nextPos) / 2,
                y2: plotTop + plotHeight,
              },
              style: {
                stroke: '#666',
                lineDash: [5, 5],
                lineWidth: 1,
              },
              z: 2,
            },
          ]
        : [];

    const graphics = [
      ...topLevelGraphics,
      ...scopeGraphics,
      ...separatorGraphics,
    ];
    chartInstance.setOption({ graphic: graphics });
  };

  // Update graphics after chart renders
  setTimeout(updateScopeGraphics, 100);

  resizeHandler = () => {
    chartInstance?.resize();
    setTimeout(updateScopeGraphics, 100);
  };
  window.addEventListener('resize', resizeHandler);
};

onMounted(() => {
  initChart();
});

// Watch for colorblind mode changes and update chart
watch(colorblindMode, () => {
  if (chartInstance) {
    initChart();
  }
});

// Watch for locale changes and update chart to refresh translations
watch(locale, () => {
  if (chartInstance) {
    initChart();
  }
});

// Cleanup on component unmount
onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler);
    resizeHandler = null;
  }
});
</script>

<template>
  <div ref="chartRef" style="width: 100%; min-height: 500px"></div>
</template>
