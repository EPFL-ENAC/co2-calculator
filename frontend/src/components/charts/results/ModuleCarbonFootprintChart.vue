<script setup lang="ts">
import { computed, ref, onMounted, watch, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import type { EChartsOption, BarSeriesOption } from 'echarts';
import type { ECharts } from 'echarts/core';
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
} from 'echarts/components';
import VChart from 'vue-echarts';
import { getElement, colorblindMode } from 'src/constant/charts';

use([
  CanvasRenderer,
  BarChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  GraphicComponent,
]);

const chartRef = ref<ECharts>();
const graphicsRef = ref<EChartsOption['graphic']>([]);
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

// Build chart data and mappings
const buildChartData = () => {
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

  return {
    barLabels,
    translatedNameToelementId,
    barToSubCategories,
    subCategoryToMainCategory,
    dataset,
    subCategories,
  };
};

// Color helpers
const getColor = (elementId: string, shade: number = 2): string =>
  getElement(elementId, shade);

const getSubCategoryColor = (
  subCategory: string,
  index: number,
  subCategoryToMainCategory: Record<string, string>,
): string => {
  const mainCategory = subCategoryToMainCategory[subCategory] || subCategory;
  const categoryConfig = categories.find((c) => c.elementId === mainCategory);
  // If category has a single value (no subcategories), use middle shade (2)
  const shade = categoryConfig?.value !== undefined ? 2 : Math.min(index, 4);
  return getColor(mainCategory, shade);
};

// Build top-level category labels (Calculated, Estimated)
const buildTopLevelGraphics = (
  chart: ECharts,
  barLabels: string[],
  plotTop: number,
  barWidth: number,
) => {
  const topLevelCategories = [
    { label: t('charts-calculated'), startIndex: 0, endIndex: 7 },
    { label: t('charts-estimated'), startIndex: 8, endIndex: 11 },
  ];

  return topLevelCategories
    .map((category) => {
      const startPos = chart.convertToPixel(
        'xAxis',
        barLabels[category.startIndex],
      );
      const endPos = chart.convertToPixel(
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
    })
    .filter((g) => g !== null);
};

// Build scope graphics array
const buildScopeGraphics = (
  chart: ECharts,
  barLabels: string[],
  plotTop: number,
  plotHeight: number,
  barWidth: number,
) => {
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

  return scopeAreas
    .map((scope) => {
      const startPos = chart.convertToPixel(
        'xAxis',
        barLabels[scope.startIndex],
      );
      const endPos = chart.convertToPixel('xAxis', barLabels[scope.endIndex]);

      if (startPos == null || endPos == null || !barWidth) {
        return [];
      }

      const startX = startPos - barWidth / 2;
      const endX = endPos + barWidth / 2;
      const width = endX - startX;

      return [
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
          z: -1,
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
};

// Build separator line after Scope 3
const buildSeparatorGraphics = (
  chart: ECharts,
  barLabels: string[],
  plotTop: number,
  plotHeight: number,
) => {
  const separatorPos = chart.convertToPixel('xAxis', barLabels[7]);
  const nextPos = chart.convertToPixel('xAxis', barLabels[8]);

  if (!separatorPos || !nextPos) return [];

  return [
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
  ];
};

// Update scope graphics after chart renders
const updateScopeGraphics = () => {
  if (!chartRef.value) return;

  const chartData = buildChartData();
  const { barLabels } = chartData;

  // Get plot area bounds from option
  const option = chartRef.value.getOption() as EChartsOption;
  const grid =
    (Array.isArray(option.grid) ? option.grid[0] : option.grid) || {};
  const gridTop = parseFloat(String(grid.top || '0%').replace('%', '')) || 0;
  const gridBottom =
    parseFloat(String(grid.bottom || '15%').replace('%', '')) || 15;
  const chartHeight = chartRef.value.getHeight();
  const plotTop = (chartHeight * gridTop) / 100;
  const plotBottom = chartHeight - (chartHeight * gridBottom) / 100;
  const plotHeight = plotBottom - plotTop;

  const firstPos = chartRef.value.convertToPixel('xAxis', barLabels[0]);
  const secondPos = chartRef.value.convertToPixel('xAxis', barLabels[1]);
  const barWidth = firstPos && secondPos ? Math.abs(secondPos - firstPos) : 0;

  const topLevelGraphics = buildTopLevelGraphics(
    chartRef.value,
    barLabels,
    plotTop,
    barWidth,
  );
  const scopeGraphics = buildScopeGraphics(
    chartRef.value,
    barLabels,
    plotTop,
    plotHeight,
    barWidth,
  );
  const separatorGraphics = buildSeparatorGraphics(
    chartRef.value,
    barLabels,
    plotTop,
    plotHeight,
  );

  const graphics = [
    ...topLevelGraphics,
    ...scopeGraphics,
    ...separatorGraphics,
  ];

  if (graphics.length > 0 && barWidth > 0) {
    graphicsRef.value = graphics;
    chartRef.value.setOption({ graphic: graphics }, { notMerge: false });
  }
};

// Computed chart option
const chartOption = computed<EChartsOption>(() => {
  const chartData = buildChartData();
  const {
    barLabels,
    translatedNameToelementId,
    barToSubCategories,
    subCategoryToMainCategory,
    dataset,
    subCategories,
  } = chartData;

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

  // Get and sort subcategories with data for proper stacking
  const sortedSubCategories = subCategories
    .filter((sub) =>
      dataset.source.some((row) => {
        return row[sub];
      }),
    )
    .sort((a, b) => {
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
          color: getSubCategoryColor(
            subCategory,
            index >= 0 ? index : 0,
            subCategoryToMainCategory,
          ),
        },
        emphasis: {
          itemStyle: {
            color: getSubCategoryColor(
              subCategory,
              index >= 0 ? index : 0,
              subCategoryToMainCategory,
            ),
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

  return {
    dataset: [dataset],
    graphic: graphicsRef.value as EChartsOption['graphic'],
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

        // Get elementId from translated name
        const elementId = translatedNameToelementId[categoryName];

        const subCats = barToSubCategories[elementId];
        const subCategoryData = [];

        let categoryTotal = 0;

        subCats.forEach((subCat) => {
          const value = categoryRow[subCat];

          const mainCategoryelementId = subCategoryToMainCategory[subCat];
          const subCatsForCategory = barToSubCategories[mainCategoryelementId];
          const index = subCatsForCategory.indexOf(subCat);
          const color = getSubCategoryColor(
            subCat,
            index,
            subCategoryToMainCategory,
          );

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
      name: t('tco2eq'),
      nameLocation: 'middle',
      nameGap: 30,
      nameRotate: 90,
      nameTextStyle: { fontSize: 10, fontWeight: 'bold' },
      max: calculateMaxValue(),
      splitLine: { show: true, lineStyle: { color: '#E0E0E0', type: 'solid' } },
    },
    series: [...legendSeries, ...categorySeries],
  };
});

// Watch for chart instance and update graphics after render
watch(
  () => chartRef.value,
  (newInstance) => {
    if (newInstance) {
      // Wait for chart to be fully rendered
      nextTick(() => {
        setTimeout(() => {
          updateScopeGraphics();
        }, 300);
      });
    }
  },
  { immediate: true },
);

// Watch for chartOption changes and update graphics
watch(
  () => chartOption.value,
  () => {
    if (chartRef.value) {
      // Delay to ensure chart has rendered with new option
      nextTick(() => {
        setTimeout(() => {
          updateScopeGraphics();
        }, 500);
      });
    }
  },
  { flush: 'post' },
);

// Watch for colorblind mode changes and update graphics
watch(colorblindMode, () => {
  if (chartRef.value) {
    nextTick(() => {
      setTimeout(() => {
        updateScopeGraphics();
      }, 300);
    });
  }
});

// Watch for locale changes and update graphics
watch(locale, () => {
  if (chartRef.value) {
    nextTick(() => {
      setTimeout(() => {
        updateScopeGraphics();
      }, 300);
    });
  }
});

// Update graphics on mount after chart is ready
onMounted(() => {
  nextTick(() => {
    setTimeout(() => {
      updateScopeGraphics();
    }, 300);
  });
});
</script>

<template>
  <v-chart ref="chartRef" class="chart" autoresize :option="chartOption" />
</template>

<style scoped>
.chart {
  width: 100%;
  min-height: 500px;
}
</style>
