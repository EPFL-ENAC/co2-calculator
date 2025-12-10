<script setup lang="ts">
import { ref, onMounted } from 'vue';
import * as echarts from 'echarts';
import type { EChartsOption, BarSeriesOption } from 'echarts';
import { getElementColor } from 'src/constant/chart-colors';

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

interface CategoryConfig {
  name: string;
  colorId: string;
  subCategories?: string[];
}

const categoryConfigs: CategoryConfig[] = [
  { name: 'Unit-gas', colorId: 'unit-gas' },
  { name: 'Infrastructure-gas', colorId: 'infrastructure-gas' },
  {
    name: 'Infrastructure',
    colorId: 'infrastructure-category',
    subCategories: ['Heating', 'Cooling', 'Ventilation', 'Lighting'],
  },
  {
    name: 'Equipment',
    colorId: 'equipment',
    subCategories: ['Scientific', 'IT Equipment', 'Other'],
  },
  { name: 'Commuting', colorId: 'commuting' },
  { name: 'Food', colorId: 'food' },
  {
    name: 'Professional Travel',
    colorId: 'professional-travel-category',
    subCategories: ['Train', 'Plane'],
  },
  { name: 'IT', colorId: 'it' },
  {
    name: 'Research Core Facilities',
    colorId: 'research-core-facilities',
    subCategories: ['SCITAS', 'RCP'],
  },
  {
    name: 'Purchases',
    colorId: 'purchases',
    subCategories: [
      'Bio-chemicals',
      'Consumables',
      'Equipment',
      'Services',
      'Other Purchases',
    ],
  },
  { name: 'Waste', colorId: 'waste' },
  { name: 'Grey Energy', colorId: 'grey-energy', subCategories: ['PH', 'GC'] },
];

const barLabels = categoryConfigs.map((c) => c.name);

// Build mappings
const barToSubCategories: Record<string, string[]> = {};
const subCategoryToMainCategory: Record<string, string> = {};
const allSubCategories = new Set<string>();

categoryConfigs.forEach((config) => {
  const subCats = config.subCategories?.length
    ? config.subCategories
    : [config.name];
  barToSubCategories[config.name] = subCats;
  subCats.forEach((sub) => {
    subCategoryToMainCategory[sub] = config.name;
    allSubCategories.add(sub);
  });
});

const subCategories = Array.from(allSubCategories);

// Build dataset source
const buildDatasetSource = (): Record<string, string | number | null>[] => {
  const source = barLabels.map((bar) => {
    const row: Record<string, string | number | null> = { bar };
    subCategories.forEach((sub) => (row[sub] = null));
    return row;
  });

  // Set data values
  source[0]['Unit-gas'] = 2.5;
  source[1]['Infrastructure-gas'] = 2.0;
  source[2]['Heating'] = 9.0;
  source[2]['Cooling'] = 3.0;
  source[2]['Ventilation'] = 9.0;
  source[2]['Lighting'] = 3.0;
  source[3]['Scientific'] = 10.0;
  source[3]['IT Equipment'] = 3.0;
  source[4]['Commuting'] = 8.0;
  source[5]['Food'] = 2.5;
  source[6]['Train'] = 1.5;
  source[6]['Plane'] = 3.0;
  source[7]['IT'] = 25.0;
  source[8]['SCITAS'] = 1.0;
  source[8]['RCP'] = 1.5;
  source[9]['Bio-chemicals'] = 2.0;
  source[9]['Consumables'] = 3.0;
  source[9]['Equipment'] = 1.0;
  source[9]['Services'] = 2.0;
  source[9]['Other Purchases'] = 0.2;
  source[10]['Waste'] = 10.0;
  source[11]['GC'] = 4.0;
  source[11]['PH'] = 4.0;

  return source;
};

const dataset = {
  dimensions: ['bar', ...subCategories],
  source: buildDatasetSource(),
};

// Scope configurations
const scopeAreas = [
  { label: 'Scope 1', color: '#F5F5F5', range: [0, 1] },
  { label: 'Scope 2', color: '#E8E8E8', range: [2, 3] },
  { label: 'Scope 3', color: '#D0D0D0', range: [4, 9] },
  { label: 'Estimated', color: '#D0D0D0', range: [10, 11] },
];

const getColor = (categoryName: string, shade: number = 2): string => {
  const config = categoryConfigs.find((c) => c.name === categoryName);
  return getElementColor(config.colorId, shade);
};

const getSubCategoryColor = (subCategory: string, index: number): string => {
  const mainCategory = subCategoryToMainCategory[subCategory] || subCategory;
  const shade = mainCategory === subCategory ? 2 : Math.min(index, 4);
  return getColor(mainCategory, shade);
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
        encode: { x: 'bar', y: subCategory },
        stack: 'total',
        barWidth: '80%',

        itemStyle: {
          color: getSubCategoryColor(subCategory, index >= 0 ? index : 0),
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
    silent: true,
    tooltip: { show: false },
    legendHoverLink: true,
  }));

  // Create scope markArea series
  const scopeSeries: BarSeriesOption[] = scopeAreas.map((scope) => ({
    type: 'bar',
    data: [],
    markArea: {
      silent: true,
      itemStyle: { color: scope.color, opacity: 0.3 },
      label: {
        show: true,
        position: 'insideTop',
        formatter: scope.label,
        fontSize: 12,
        fontWeight: 'bold',
        color: '#333',
      },
      data: [[{ xAxis: scope.range[0] }, { xAxis: scope.range[1] }]],
    },
    z: 0,
  }));

  // Separator line
  const separatorSeries: BarSeriesOption = {
    type: 'bar',
    data: [],
    markLine: {
      silent: true,
      symbol: 'none',
      lineStyle: { color: '#666', type: 'dashed', width: 2 },
      data: [
        [
          { xAxis: 9.5, yAxis: 0 },
          { xAxis: 9.5, yAxis: 35 },
        ],
      ],
    },
    z: 10,
  };

  const option: EChartsOption = {
    dataset: [dataset],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      position: (
        point: number[],
        _params: unknown,
        _dom: unknown,
        _rect: unknown,
        size: { viewSize: number[]; contentSize: number[] },
      ) => [
        point[0] - size.contentSize[0] / 2,
        point[1] - size.contentSize[1] - 10,
      ],
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

        // Get all subcategories for this category
        const subCats = barToSubCategories[categoryName] || [];

        // Collect all subcategory values for this category
        const subCategoryData: Array<{
          name: string;
          value: number;
          color: string;
        }> = [];

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
      left: '10%',
      right: '10%',
      bottom: '15%',
      top: '0%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      axisLabel: { show: false },
      boundaryGap: false,
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 't CO₂-eq',
      nameLocation: 'middle',
      nameGap: 50,
      nameRotate: 90,
      nameTextStyle: { fontSize: 10, fontWeight: 'normal' },
      max: 35,
      splitLine: { show: true, lineStyle: { color: '#E0E0E0', type: 'solid' } },
    },
    series: [
      ...scopeSeries,
      separatorSeries,
      ...legendSeries,
      ...categorySeries,
    ],
  };

  chartInstance.setOption(option);

  const handleResize = () => chartInstance?.resize();
  window.addEventListener('resize', handleResize);
};

onMounted(() => {
  initChart();
});
</script>

<template>
  <div
    ref="chartRef"
    style="width: 100%; height: 500px; min-height: 500px"
  ></div>
</template>
