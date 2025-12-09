<script setup lang="ts">
import { ref, onMounted } from 'vue';
import * as echarts from 'echarts';
import type { EChartsOption, BarSeriesOption } from 'echarts';
import { getElementColor } from 'src/constant/chart-colors';

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

// Category colors using the chart color scale utility
const categoryColors: Record<string, string> = {
  'Unit-gas': getElementColor('unit-gas'),
  'Infrastructure-gas': getElementColor('infrastructure-gas'),
  Infrastructure: getElementColor('infrastructure-category'),
  Equipment: getElementColor('equipment'),
  Commuting: getElementColor('commuting'),
  Food: getElementColor('food'),
  'Professional Travel': getElementColor('professional-travel-category'),
  IT: getElementColor('it'),
  'Research Core Facilities': getElementColor('research-core-facilities'),
  Purchases: getElementColor('purchases'),
  Waste: getElementColor('waste'),
  'Grey Energy': getElementColor('grey-energy'),
};

// Categories list
const categories = [
  'Unit-gas',
  'Infrastructure-gas',
  'Infrastructure',
  'Equipment',
  'Commuting',
  'Food',
  'Professional Travel',
  'IT',
  'Research Core Facilities',
  'Purchases',
  'Waste',
  'Grey Energy',
];

// Bar labels for x-axis
const barLabels = [
  'Unit-gas',
  'Infrastructure-gas',
  'Infrastructure',
  'Equipment',
  'Commuting',
  'Food',
  'Professional Travel',
  'IT',
  'Research Core Facilities',
  'Purchases',
  'Waste',
  'Grey Energy',
];

// Collect all sub-categories used in the data
const subCategories = [
  'Unit-gas',
  'Infrastructure-gas',
  'Professional Travel',
  'Purchases',
  'Equipment',
  'Research Core Facilities',
  'IT',
  'Food',
  'Commuting',
  'Train',
  'Plane',
  'SCITAS',
  'RCP',
  'Bio-chemicals',
  'Consumables',
  'Services',
  'Other',
  'Waste',
  'GC',
  'PH',
  'Heating',
  'Cooling',
  'Ventilation',
  'Lighting',
  'Scientific',
];

// Build dataset source: each row represents a bar, columns represent sub-categories
const buildDatasetSource = (): Record<string, string | number | null>[] => {
  const source: Record<string, string | number | null>[] = [];

  // Initialize all bars with null values for all sub-categories
  for (let barIndex = 0; barIndex < barLabels.length; barIndex++) {
    const barData: Record<string, string | number | null> = {
      bar: barLabels[barIndex],
    };
    subCategories.forEach((subCategory) => {
      barData[subCategory] = null;
    });
    source.push(barData);
  }

  // Bar 0: Unit-gas
  source[0]['Unit-gas'] = 2.5;

  // Bar 1: Infrastructure-gas
  source[1]['Infrastructure-gas'] = 2.0;

  // Bar 2: Infrastructure
  source[2]['Heating'] = 9.0;
  source[2]['Cooling'] = 3.0;
  source[2]['Ventilation'] = 9.0;
  source[2]['Lighting'] = 3.0;

  // Bar 3: Equipment
  source[3]['Scientific'] = 10.0;
  source[3]['IT'] = 3.0;
  source[3]['Other'] = 0.2;

  // Bar 4: Commuting
  source[4]['Commuting'] = 8.0;

  // Bar 5: Food
  source[5]['Food'] = 2.5;

  // Bar 6: Professional Travel
  source[6]['Train'] = 1.5;
  source[6]['Plane'] = 3.0;

  // Bar 7: IT
  source[7]['IT'] = 25.0;

  // Bar 8: Research Core Facilities
  source[8]['SCITAS'] = 1.0;
  source[8]['RCP'] = 1.5;

  // Bar 9: Purchases
  source[9]['Bio-chemicals'] = 2.0;
  source[9]['Consumables'] = 3.0;
  source[9]['Equipment'] = 1.0;
  source[9]['Services'] = 2.0;
  source[9]['Other'] = 0.2;

  // Bar 10: Waste
  source[10]['Waste'] = 10.0;

  // Bar 11: Grey Energy
  source[11]['GC'] = 4.0;
  source[11]['PH'] = 4.0;

  return source;
};

// Create dataset configuration
const dataset = {
  dimensions: ['bar', ...subCategories],
  source: buildDatasetSource(),
};

const initChart = () => {
  if (!chartRef.value) return;

  chartInstance = echarts.init(chartRef.value);

  // Map main categories (bars) to their sub-categories
  const barToSubCategories: Record<string, string[]> = {
    'Unit-gas': ['Unit-gas'],
    'Infrastructure-gas': ['Infrastructure-gas'],
    Infrastructure: ['Heating', 'Cooling', 'Ventilation', 'Lighting'],
    Equipment: ['Scientific', 'IT', 'Other'],
    Commuting: ['Commuting'],
    Food: ['Food'],
    'Professional Travel': ['Train', 'Plane'],
    IT: ['IT'],
    'Research Core Facilities': ['SCITAS', 'RCP'],
    Purchases: [
      'Bio-chemicals',
      'Consumables',
      'Equipment',
      'Services',
      'Other',
    ],
    Waste: ['Waste'],
    'Grey Energy': ['GC', 'PH'],
  };

  // Find sub-categories that have at least one non-null value in the dataset
  const subCategoriesWithData = subCategories.filter((subCategory) => {
    return dataset.source.some((row) => {
      const value = (row as Record<string, unknown>)[subCategory];
      return value !== null && value !== undefined && value !== 0;
    });
  });

  // Find which main category each sub-category belongs to
  const subCategoryToMainCategory: Record<string, string> = {};
  Object.entries(barToSubCategories).forEach(([mainCategory, subCats]) => {
    subCats.forEach((subCat) => {
      subCategoryToMainCategory[subCat] = mainCategory;
    });
  });

  // Create series only for sub-categories that have data (these are hidden from legend)
  const categorySeries: BarSeriesOption[] = subCategoriesWithData.map(
    (subCategory) => {
      // Try to find a color for this sub-category, fallback to a default
      let color = categoryColors[subCategory];
      if (!color) {
        // If sub-category doesn't have a direct color, try to find it in categories
        const mainCategory = categories.find((cat) => cat === subCategory);
        color = mainCategory ? categoryColors[mainCategory] : '#999999';
      }

      return {
        name: subCategory,
        type: 'bar',
        datasetIndex: 0,
        encode: {
          x: 'bar',
          y: subCategory,
        },
        stack: 'total',
        barWidth: '70%',
        barCategoryGap: '20%',
        itemStyle: {
          color: color,
        },
      };
    },
  );

  // Create placeholder series for main categories (only for legend display)
  // Use barLabels order to ensure same order as bars
  const legendSeries: BarSeriesOption[] = barLabels.map((mainCategory) => {
    const color = categoryColors[mainCategory] || '#999999';
    return {
      name: mainCategory,
      type: 'bar',
      data: [],
      itemStyle: {
        color: color,
      },
      // These series don't render but appear in legend
      silent: true,
      tooltip: {
        show: false,
      },
      // Make sure they appear in legend
      legendHoverLink: true,
    };
  });

  const option: EChartsOption = {
    dataset: [dataset],
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      formatter: (params: unknown) => {
        if (Array.isArray(params) && params.length > 0) {
          const firstParam = params[0] as {
            axisValue?: string;
            marker?: string;
            seriesName?: string;
            value?: number | null;
            color?: string;
          };
          if (!firstParam) {
            return '';
          }
          const axisValue = firstParam.axisValue || '';
          let result = `<b>${axisValue}</b><br/>`;
          let total = 0;

          // Filter and sort params to show only non-null values
          const validParams = params.filter((param) => {
            const p = param as {
              value?: number | null;
            };
            return (
              p &&
              p.value !== null &&
              p.value !== undefined &&
              typeof p.value === 'number' &&
              p.value > 0
            );
          }) as Array<{
            marker?: string;
            seriesName?: string;
            value?: number | null;
            color?: string;
          }>;

          validParams.forEach((param) => {
            if (
              param.value !== null &&
              param.value !== undefined &&
              typeof param.value === 'number'
            ) {
              result += `${param.marker || '●'} <span style="color: ${param.color || '#333'}">${param.seriesName || ''}</span>: ${param.value.toFixed(1)} t CO₂-eq<br/>`;
              total += param.value;
            }
          });

          if (validParams.length > 0) {
            result += `<br/><b>Total: ${total.toFixed(1)} t CO₂-eq</b>`;
          }

          return result;
        }
        return '';
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
    },
    grid: {
      left: '10%',
      right: '4%',
      bottom: '15%',
      top: '0%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      axisLabel: {
        show: false,
      },
      boundaryGap: true,
    },
    yAxis: {
      type: 'value',
      name: 't CO₂-eq',
      nameLocation: 'middle',
      nameGap: 50,
      nameRotate: 90,
      nameTextStyle: {
        fontSize: 10,
        fontWeight: 'normal',
      },
      max: 35,
      splitLine: {
        show: true,
        lineStyle: {
          color: '#E0E0E0',
          type: 'solid',
        },
      },
    },
    series: [
      // Background areas for scopes (progressively greyer)
      {
        type: 'bar',
        data: [],
        markArea: {
          silent: true,
          itemStyle: {
            color: '#F5F5F5', // Light grey for Scope 1
            opacity: 0.3,
          },
          label: {
            show: true,
            position: [0.5, 0], // Center of xAxis 0-1, at top
            formatter: 'Scope 1',
            fontSize: 12,
            fontWeight: 'bold',
            color: '#333',
          },
          data: [
            [{ xAxis: 0 }, { xAxis: 1 }], // Scope 1 (bars 0-1)
          ],
        },
        z: 0,
      } as BarSeriesOption,
      {
        type: 'bar',
        data: [],
        markArea: {
          silent: true,
          itemStyle: {
            color: '#E8E8E8', // Medium grey for Scope 2
            opacity: 0.3,
          },
          label: {
            show: true,
            position: [2.5, 0],
            formatter: 'Scope 2',
            fontSize: 12,
            fontWeight: 'bold',
            color: '#333',
          },
          data: [
            [{ xAxis: 2 }, { xAxis: 3 }], // Scope 2 (bars 2-3)
          ],
        },
        z: 0,
      } as BarSeriesOption,
      {
        type: 'bar',
        data: [],
        markArea: {
          silent: true,
          itemStyle: {
            color: '#D0D0D0', // Darker grey for Scope 3
            opacity: 0.3,
          },
          label: {
            show: true,
            position: [6.5, 0], // Center of xAxis 4-9, at top
            formatter: 'Scope 3',
            fontSize: 12,
            fontWeight: 'bold',
            color: '#333',
          },
          data: [
            [{ xAxis: 4 }, { xAxis: 9 }], // Scope 3 (bars 4-9)
          ],
        },
        z: 0,
      } as BarSeriesOption,
      {
        type: 'bar',
        data: [],
        markArea: {
          silent: true,
          itemStyle: {
            color: '#D0D0D0', // Darkest grey for Estimated (darker than Scope 3)
            opacity: 0.3,
          },
          label: {
            show: true,
            position: [13.5, 0], // Center of xAxis 10-13, at top
            formatter: 'Estimated',
            fontSize: 12,
            fontWeight: 'bold',
            color: '#333',
          },
          data: [
            [{ xAxis: 10 }, { xAxis: 13 }], // Estimated (bars 10-13)
          ],
        },
        z: 0,
      } as BarSeriesOption,
      // Dotted line separator between Scope 3 and Estimated
      {
        type: 'bar',
        data: [],
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            color: '#666',
            type: 'dashed',
            width: 2,
          },
          data: [
            [
              {
                xAxis: 10, // Between bar 9 (last Scope 3) and bar 10 (first Estimated)
                yAxis: 0,
              },
              {
                xAxis: 10,
                yAxis: 35, // Full height
              },
            ],
          ],
        },
        z: 10,
      } as BarSeriesOption,

      ...legendSeries, // Main categories for legend
      ...categorySeries, // Sub-categories for actual bars (hidden from legend)
    ],
  };

  chartInstance.setOption(option);

  // Handle legend clicks to show/hide bars
  chartInstance.on(
    'legendselectchanged',
    (params: { selected: Record<string, boolean>; name: string }) => {
      const mainCategory = params.name;
      const isSelected = params.selected[mainCategory];

      // Find the bar index for this main category
      const barIndex = barLabels.indexOf(mainCategory);
      if (barIndex === -1) return;

      // Get the bar data row from the dataset
      const barData = dataset.source[barIndex] as Record<string, unknown>;

      // Find all sub-categories that have data in this specific bar
      const subCatsInThisBar: string[] = [];
      subCategories.forEach((subCat) => {
        const value = barData[subCat];
        if (value !== null && value !== undefined && value !== 0) {
          subCatsInThisBar.push(subCat);
        }
      });

      // Build update object for all sub-categories in this bar
      const selectedUpdate: Record<string, boolean> = {};
      subCatsInThisBar.forEach((subCat) => {
        selectedUpdate[subCat] = isSelected;
      });

      // Update sub-category series visibility
      chartInstance?.dispatchAction({
        type: 'legendSelect',
        selected: selectedUpdate,
      });
    },
  );

  // Handle window resize
  const handleResize = () => {
    chartInstance?.resize();
  };
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
