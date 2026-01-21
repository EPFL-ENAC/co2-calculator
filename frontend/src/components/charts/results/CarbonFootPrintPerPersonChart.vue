<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { use } from 'echarts/core';
  import { CanvasRenderer } from 'echarts/renderers';
  import { BarChart } from 'echarts/charts';
  import type { EChartsOption } from 'echarts';
  import { graphic } from 'echarts';
  import { colors } from 'src/constant/charts';
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
  
  
  const { t } = useI18n();
  const toggleAdditionalData = ref(false);
  const viewUncertainties = ref(false);


  const datasetSource = computed(() => {
    const baseData = [
      {
        category: t('charts-my-unit-tick'),
        unitGas: 2.5,
        infrastructureGas: 2,
        infrastructure: 4,
        equipment: 1,
        itInfrastructure: 25,
        professionalTravel: 1.5,
        purchases: 2,
        researchCoreFacilities: 1,
        commuting: 8,
        food: 2.5,
        waste: 10,
        greyEnergy: 4,

      },
      {
        category: t('charts-epf-tick'),
        unitGas: 2.3,
        infrastructureGas: 2.2,
        infrastructure: 4.1,
        equipment: 0.9,
        itInfrastructure: 24.5,
        professionalTravel: 1.6,
        purchases: 2.1,
        researchCoreFacilities: 1.1,
        commuting: 7.8,
        food: 2.4,
        waste: 10.2,
        greyEnergy: 3.9,
      },
      {
          category: t('charts-objective-tick'),
          objective2030: 52,
        
      },
    ];
    return baseData;
  });
  

  const additionalSeriesData = computed(() => {
    if (!toggleAdditionalData.value) return [];

    return [
      {
        name: t('charts-commuting-category'),
        type: 'bar' as const,
        stack: 'total',
        encode: {
          x: 'category',
          y: 'commuting',
        },
        itemStyle: {
          color: colors.value.skyBlue.darker,
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-food-category'),
        type: 'bar' as const,
        stack: 'total',
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
        encode: {
          x: 'category',
          y: 'greyEnergy',
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
  
  const chartOption = computed((): EChartsOption => {
  
    // Build series array first (will be used to extract mapping)
    const seriesArray = [
      {
        name: t('charts-unit-gas-category'),
        type: 'bar' as const,
        stack: 'total',
        encode: {
          x: 'category',
          y: 'unitGas',
        },
        markLine: {
          silent: true,
          symbol: ['none', 'none'],
          lineStyle: {
            color: '#333',
            width: 1.5,
            type: 'solid' as const,
          },
          data: [],
        },
        itemStyle: {
          color: colors.value.peach.darker,
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-infrastructure-gas-category'),
        type: 'bar' as const,
        stack: 'total',
        encode: {
          x: 'category',
          y: 'infrastructureGas',
        },
        itemStyle: {
          color: colors.value.apricot.darker,
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-infrastructure-category'),
        type: 'bar' as const,
        stack: 'total',
        encode: {
          x: 'category',
          y: 'infrastructure',
        },
        itemStyle: {
          color: colors.value.lilac.darker,
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-equipment-category'),
        type: 'bar' as const,
        stack: 'total',
        encode: {
          x: 'category',
          y: 'equipment',
        },
        itemStyle: {
          color: colors.value.mauve.darker,
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-it-category'),
        type: 'bar' as const,
        stack: 'total',
        encode: {
          x: 'category',
          y: 'itInfrastructure',
        },
        itemStyle: {
          color: colors.value.lavender.darker,
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-professional-travel-category'),
        type: 'bar' as const,
        stack: 'total',
        encode: {
          x: 'category',
          y: 'professionalTravel',
        },
        itemStyle: {
          color: colors.value.babyBlue.darker,
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-purchases-category'),
        type: 'bar' as const,
        stack: 'total',
        encode: {
          x: 'category',
          y: 'purchases',
        },
        itemStyle: {
          color: colors.value.lightGreen.darker,
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-research-core-facilities-category'),
        type: 'bar' as const,
        stack: 'total',
        encode: {
          x: 'category',
          y: 'researchCoreFacilities',
        },
        itemStyle: {
          color: colors.value.paleYellowGreen.darker,
        },
        label: {
          show: false,
        },
      },
      {
        name: t('charts-objective-tick'),
        type: 'bar' as const,
        stack: 'total',
        encode: {
          x: 'category',
          y: 'objective2030',
        },
        itemStyle: {
          color: colors.value.skyBlue.darker,
        },
        label: {
          show: false,
        },
      },
      ...additionalSeriesData.value,
    ];
  
    return {
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
          let total = 0;
          let tooltip = `<strong>${name}</strong><br/>`;
  
          if (arr.length > 1) {
            arr.reverse().forEach((param: unknown) => {
              const p = param as {
                seriesName?: string;
                marker?: string;
                value?: number | number[];
                data?: Record<string, unknown>;
              };
              // Find series by name to get its key
              const series = seriesArray.find((s) => s.name === p.seriesName);
              const key = series?.encode.y;
  
              const dataValue = Number(data[key]) || 0;
              if (dataValue > 0) {
                tooltip += `${p.marker || ''} ${series?.name || p.seriesName || ''}: <strong>${dataValue.toFixed(1)} </strong><br/>`;
                total += dataValue;
              }
            });
          } else {
            // If only one item, calculate total from all series
            arr.reverse().forEach((param: unknown) => {
              const p = param as {
                seriesName?: string;
                data?: Record<string, unknown>;
              };
              const series = seriesArray.find((s) => s.name === p.seriesName);
              const key = series?.encode.y;
              const dataValue = Number(data[key]) || 0;
              total += dataValue;
            });
          }
  
          const totalDisplay = total.toFixed(1);
          if (viewUncertainties.value && data) {
            // TODO: Add uncertainty calculation
          }
  
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
          fontSize: 11,
        },
      },
      yAxis: {
        type: 'value',
        name: t('tco2eq'),
        nameLocation: 'middle',
        nameGap: 30,
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
        {
          type: 'rect',
          left: '46px',
          top: '15px',
          shape: {
            width: 500,
            height: 300,
          },
          style: {
            fill: new graphic.LinearGradient(0, 0, 0, 1, [
              {
                offset: 0,
                color: 'rgba(240,240,240,0.9)',
              },
              {
                offset: 1,
                color: 'rgba(240,240,240,0.1)',
              },
            ]),
          },
        },
        {
          type: 'rect',
          left: '335px',
          top: '0px',
          shape: {
            width: 1,
            height: 420,
          },
          style: {
            fill: new graphic.LinearGradient(0, 0, 0, 1, [
              {
                offset: 0,
                color: 'rgba(0,0,0)',
              },
              {
                offset: 1,
                color: 'rgba(240,240,240,0.1)',
              },
            ]),
          },
          z: 100,
        },
       
      ],
      dataset: {
        dimensions: [
          'category',
          'unitGas',
          'infrastructureGas',
          'cooling',
          'ventilation',
          'lighting',
          'scientific',
          'it',
          'other',
          'train',
          'plane',
          'itInfrastructure',
          'bioChemicals',
          'consumables',
          'equipment',
          'services',
          'scitas',
          'rcp',
          'commuting',
          'food',
          'waste',
          'greyEnergy',
          'objective2030',
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
      ...new Set(datasetSource.value.flatMap((item) => Object.keys(item))),
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
            {{ $t('results_carbon_footprint_per_person_title') }}
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
  