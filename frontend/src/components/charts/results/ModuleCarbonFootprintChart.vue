<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import * as echarts from 'echarts';
import type { EChartsOption, BarSeriesOption } from 'echarts';
import { getElementColor, colorblindMode } from 'src/constant/chart-colors';

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

interface CategoryConfig {
  name: string;
  colorId: string;
  subCategories?: string[];
  value?: number;
  values?: Record<string, number>;
}

// Category configurations
const categories: CategoryConfig[] = [
  { name: 'Unit-gas', colorId: 'unit-gas', value: 2.5 },
  { name: 'Infrastructure-gas', colorId: 'infrastructure-gas', value: 2.0 },
  {
    name: 'Infrastructure',
    colorId: 'infrastructure-category',
    values: { Heating: 9.0, Cooling: 3.0, Ventilation: 9.0, Lighting: 3.0 },
  },
  {
    name: 'Equipment',
    colorId: 'equipment',
    values: { Scientific: 10.0, 'IT Equipment': 3.0 },
  },
  { name: 'Commuting', colorId: 'commuting', value: 8.0 },
  { name: 'Food', colorId: 'food', value: 2.5 },
  {
    name: 'Professional Travel',
    colorId: 'professional-travel-category',
    values: { Train: 1.5, Plane: 3.0 },
  },
  { name: 'IT', colorId: 'it', value: 25.0 },
  {
    name: 'Research Core Facilities',
    colorId: 'research-core-facilities',
    values: { SCITAS: 1.0, RCP: 1.5 },
  },
  {
    name: 'Purchases',
    colorId: 'purchases',
    values: {
      'Bio-chemicals': 2.0,
      Consumables: 3.0,
      Equipment: 1.0,
      Services: 2.0,
      'Other Purchases': 0.2,
    },
  },
  { name: 'Waste', colorId: 'waste', value: 10.0 },
  {
    name: 'Grey Energy',
    colorId: 'grey-energy',
    values: { GC: 4.0, PH: 4.0 },
  },
];

// Scope configurations
const scopeAreas = [
  { label: 'Scope 1', color: '#F5F5F5', startIndex: 0, endIndex: 1 },
  { label: 'Scope 2', color: '#E8E8E8', startIndex: 2, endIndex: 3 },
  { label: 'Scope 3', color: '#D0D0D0', startIndex: 4, endIndex: 7 },
  { label: 'Estimated', color: '#D0D0D0', startIndex: 8, endIndex: 11 },
];

const barLabels = categories.map((c) => c.name);

// Build mappings - derive subCategories from values keys or use explicit subCategories
const barToSubCategories = Object.fromEntries(
  categories.map((config) => [
    config.name,
    config.subCategories?.length
      ? config.subCategories
      : config.values
        ? Object.keys(config.values)
        : [config.name],
  ]),
);

const subCategoryToMainCategory = Object.fromEntries(
  categories.flatMap((config) => {
    const subCats = barToSubCategories[config.name];
    return subCats.map((sub) => [sub, config.name]);
  }),
);

const subCategories = Object.keys(subCategoryToMainCategory);

// Build dataset
const datasetSource: Record<string, string | number>[] = categories.map(
  (config) => ({
    bar: config.name,
    ...(config.value !== undefined
      ? { [config.name]: config.value }
      : config.values || {}),
  }),
);

const dataset = {
  dimensions: ['bar', ...subCategories],
  source: datasetSource,
};

// Calculate max value for y-axis
const calculateMaxValue = (): number =>
  Math.max(
    ...dataset.source.map((row) =>
      subCategories.reduce((sum, sub) => sum + ((row[sub] as number) || 0), 0),
    ),
  ) + 10;

// Color helpers - uses global colorblindMode ref automatically
const getColor = (categoryName: string, shade: number = 2): string =>
  getElementColor(
    categories.find((c) => c.name === categoryName)?.colorId || '',
    shade,
  );

const getSubCategoryColor = (subCategory: string, index: number): string => {
  const mainCategory = subCategoryToMainCategory[subCategory] || subCategory;
  return getColor(
    mainCategory,
    mainCategory === subCategory ? 2 : Math.min(index, 4),
  );
};

const initChart = () => {
  if (!chartRef.value) return;

  chartInstance = echarts.init(chartRef.value);

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
      return {
        name: subCategory,
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
  const legendSeries: BarSeriesOption[] = barLabels.map((category) => ({
    name: category,
    type: 'bar',
    data: [],
    itemStyle: { color: getColor(category) },
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

        const subCats = barToSubCategories[categoryName];
        const subCategoryData = [];

        let categoryTotal = 0;

        subCats.forEach((subCat) => {
          const value = categoryRow[subCat];
          if (
            value !== null &&
            value !== undefined &&
            typeof value === 'number' &&
            value > 0
          ) {
            const mainCategory = subCategoryToMainCategory[subCat] || subCat;
            const subCatsForCategory = barToSubCategories[mainCategory] || [];
            const index = subCatsForCategory.indexOf(subCat);
            const color = getSubCategoryColor(subCat, index >= 0 ? index : 0);

            subCategoryData.push({
              name: subCat,
              value,
              color,
            });
            categoryTotal += value;
          }
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
          result += `<div style="display: flex; justify-content: space-between; align-items: center;"><span><span style="color: ${item.color}">●</span> <span>${item.name}</span></span> <span>${item.value.toFixed(1)}</span></div>`;
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

    // Build graphics array directly using flatMap
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
            y: plotTop + 15,
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

    // Add separator line between Scope 3 and Estimated
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

    const graphics = [...scopeGraphics, ...separatorGraphics];
    chartInstance.setOption({ graphic: graphics });
  };

  // Update graphics after chart renders
  setTimeout(updateScopeGraphics, 100);

  const handleResize = () => {
    chartInstance?.resize();
    setTimeout(updateScopeGraphics, 100);
  };
  window.addEventListener('resize', handleResize);
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
</script>

<template>
  <div
    ref="chartRef"
    style="width: 100%; height: 500px; min-height: 500px"
  ></div>
</template>
