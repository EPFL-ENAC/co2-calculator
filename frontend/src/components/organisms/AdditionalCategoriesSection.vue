<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { PieChart } from 'echarts/charts';
import type { EChartsOption } from 'echarts';
import { TooltipComponent, LegendComponent } from 'echarts/components';
import VChart from 'vue-echarts';
import {
  CHART_CATEGORY_COLOR_SCHEMES,
  CHART_SUBCATEGORY_COLOR_SCHEMES,
} from 'src/constant/charts';
import {
  buildDoughnutOption,
  legendItems,
  type DisplayEntry,
  WASTE_DISPLAY_CATEGORY,
  WASTE_DISPLAY_ORDER,
} from 'src/composables/results/useAdditionalCategoryCharts';
import type {
  EmissionBreakdownCategoryRow,
  EmbodiedEnergyCategoryEntry,
} from 'src/stores/modules';

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent]);

const props = defineProps<{
  commutingRow?: EmissionBreakdownCategoryRow | null;
  foodRow?: EmissionBreakdownCategoryRow | null;
  wasteRow?: EmissionBreakdownCategoryRow | null;
  embodiedEnergyRow?: EmissionBreakdownCategoryRow | null;
  embodiedEnergyByCategory?: EmbodiedEnergyCategoryEntry[];
  headcountValidated?: boolean;
  buildingsValidated?: boolean;
}>();

const { t, te } = useI18n();

/** Defer canvas init until the grid is near the viewport (Lighthouse / main-thread). */
const additionalGridRef = ref<HTMLElement | null>(null);
const chartsInView = shallowRef(false);
let chartVisibilityObserver: IntersectionObserver | null = null;

onMounted(() => {
  const el = additionalGridRef.value;
  const activateCharts = () => {
    chartsInView.value = true;
    chartVisibilityObserver?.disconnect();
    chartVisibilityObserver = null;
  };

  if (!el) {
    activateCharts();
    return;
  }

  const preloadPx = 200;
  const rect = el.getBoundingClientRect();
  const nearViewport =
    rect.top < window.innerHeight + preloadPx && rect.bottom > -preloadPx;
  if (nearViewport) {
    activateCharts();
    return;
  }

  if (typeof IntersectionObserver === 'undefined') {
    activateCharts();
    return;
  }

  chartVisibilityObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        activateCharts();
      }
    },
    { root: null, rootMargin: `${preloadPx}px 0px`, threshold: 0 },
  );
  chartVisibilityObserver.observe(el);
});

onBeforeUnmount(() => {
  chartVisibilityObserver?.disconnect();
  chartVisibilityObserver = null;
});

function getCategoryAccent(
  categoryKey: 'commuting' | 'food' | 'waste' | 'embodied_energy',
): string {
  return CHART_CATEGORY_COLOR_SCHEMES.value[categoryKey] ?? '#CFD4EE';
}

function getPreferredCategoryEmissions(
  categoryKey: 'commuting' | 'food' | 'waste',
  emissions: EmissionBreakdownCategoryRow['emissions'] | undefined,
) {
  const categoryEmissions = emissions ?? [];
  const subcategoryEmissions = categoryEmissions.filter(
    (emission) => emission.key !== categoryKey,
  );

  return subcategoryEmissions.length > 0
    ? subcategoryEmissions
    : categoryEmissions;
}

// ── totals (tonnes CO₂eq) ──────────────────────────────────────────────────
const commutingTotal = computed(() =>
  getPreferredCategoryEmissions(
    'commuting',
    props.commutingRow?.emissions,
  ).reduce((sum, emission) => sum + emission.value, 0),
);
const foodTotal = computed(() =>
  getPreferredCategoryEmissions('food', props.foodRow?.emissions).reduce(
    (sum, emission) => sum + emission.value,
    0,
  ),
);
const wasteTotal = computed(() =>
  getPreferredCategoryEmissions('waste', props.wasteRow?.emissions).reduce(
    (sum, emission) => sum + emission.value,
    0,
  ),
);
const embodiedEnergyTotal = computed(() =>
  (props.embodiedEnergyRow?.emissions ?? []).reduce((s, e) => s + e.value, 0),
);

// True when headcount is validated but none of the 3 categories have chart data
const headcountHasNoData = computed(
  () =>
    props.headcountValidated &&
    commutingTotal.value <= 0 &&
    foodTotal.value <= 0 &&
    wasteTotal.value <= 0,
);

// ── commuting ─────────────────────────────────────────────────────────────
// Prefer subcategory entries; fall back to the top-level entry when the
// backend only returns an aggregate (no sub-type breakdown available yet).
const commutingEntries = computed((): DisplayEntry[] => {
  const all = props.commutingRow?.emissions ?? [];
  const subcats = all.filter((e) => e.key !== 'commuting');
  const source = subcats.length > 0 ? subcats : all;
  return source.map((e) => ({
    key: e.key,
    value: e.value,
    quantity: e.quantity ?? 0,
    quantity_unit: e.quantity_unit ?? 'km',
  }));
});

const commutingCO2Option = computed(() =>
  buildDoughnutOption({ t, te }, 'commuting', commutingEntries.value, false),
);

const commutingPhysicalOption = computed(() => {
  return buildDoughnutOption(
    { t, te },
    'commuting',
    commutingEntries.value,
    true,
  );
});

// ── food ──────────────────────────────────────────────────────────────────
// Prefer subcategory entries; fall back to the top-level entry.
const foodEntries = computed((): DisplayEntry[] => {
  const all = props.foodRow?.emissions ?? [];
  const subcats = all.filter((e) => e.key !== 'food');
  const source = subcats.length > 0 ? subcats : all;
  return source.map((e) => ({
    key: e.key,
    value: e.value,
    quantity: e.quantity ?? 0,
    quantity_unit: e.quantity_unit ?? 'kg',
  }));
});

const foodCO2Option = computed(() =>
  buildDoughnutOption({ t, te }, 'food', foodEntries.value, false),
);

const foodPhysicalOption = computed(() => {
  return buildDoughnutOption({ t, te }, 'food', foodEntries.value, true);
});

// ── waste ─────────────────────────────────────────────────────────────────
// Group raw emissions to display categories using WASTE_DISPLAY_CATEGORY map.
// Entries not in the map (parent/summary entries like 'waste', 'recycling', 'biogas')
// are filtered out.
const wasteGrouped = computed((): DisplayEntry[] => {
  const co2: Record<string, number> = {};
  const qty: Record<string, number> = {};
  const unit: Record<string, string> = {};

  for (const e of props.wasteRow?.emissions ?? []) {
    const displayKey = WASTE_DISPLAY_CATEGORY[e.key];
    if (!displayKey) continue;
    co2[displayKey] = (co2[displayKey] ?? 0) + e.value;
    qty[displayKey] = (qty[displayKey] ?? 0) + (e.quantity ?? 0);
    if (e.quantity_unit && !unit[displayKey])
      unit[displayKey] = e.quantity_unit;
  }

  const grouped = WASTE_DISPLAY_ORDER.filter((k) => (co2[k] ?? 0) > 0).map(
    (k) => ({
      key: k,
      value: co2[k] ?? 0,
      quantity: qty[k] ?? 0,
      quantity_unit: unit[k] ?? 'kg',
    }),
  );

  // Fallback: when no sub-type data exists yet, show the total as one entry
  if (grouped.length === 0) {
    return (props.wasteRow?.emissions ?? [])
      .filter((e) => e.value > 0)
      .map((e) => ({
        key: e.key,
        value: e.value,
        quantity: e.quantity ?? 0,
        quantity_unit: e.quantity_unit ?? 'kg',
      }));
  }

  return grouped;
});

const wasteCO2Option = computed(() =>
  buildDoughnutOption({ t, te }, 'waste', wasteGrouped.value, false),
);

const wastePhysicalOption = computed(() => {
  return buildDoughnutOption({ t, te }, 'waste', wasteGrouped.value, true);
});

const commutingLegend = computed(() =>
  legendItems({ t, te }, 'commuting', [
    ...new Set(commutingEntries.value.map((e) => e.key)),
  ]),
);

const foodLegend = computed(() =>
  legendItems({ t, te }, 'food', [
    ...new Set(foodEntries.value.map((e) => e.key)),
  ]),
);

const wasteLegend = computed(() =>
  legendItems(
    { t, te },
    'waste',
    wasteGrouped.value.map((e) => e.key),
  ),
);

// ── embodied energy (construction & renovation) ─────────────────────────
const EMBODIED_ENERGY_CATEGORY_ORDER = [
  'new-env',
  'new-tech',
  'ren-env',
  'ren-tech',
  'demolition',
];

const embodiedEnergyByCategoryData = computed(() => {
  const entries = props.embodiedEnergyByCategory ?? [];
  const filtered = entries.filter((e) => e.tonnes_co2eq > 0);
  return EMBODIED_ENERGY_CATEGORY_ORDER.filter((cat) =>
    filtered.some((e) => e.category === cat),
  ).map((cat) => filtered.find((e) => e.category === cat)!);
});

const embodiedEnergyCO2Option = computed((): EChartsOption => {
  const entries: DisplayEntry[] = embodiedEnergyByCategoryData.value.map(
    (c) => ({
      key: c.category,
      value: c.tonnes_co2eq,
      quantity: 0,
      quantity_unit: 'kg',
    }),
  );
  return buildDoughnutOption({ t, te }, 'embodied_energy', entries, false);
});

const embodiedEnergyLegend = computed(() =>
  embodiedEnergyByCategoryData.value.map((c) => ({
    key: c.category,
    label: te(`charts-${c.category.replace(/_/g, '-')}-subcategory`)
      ? t(`charts-${c.category.replace(/_/g, '-')}-subcategory`)
      : c.category,
    color:
      CHART_SUBCATEGORY_COLOR_SCHEMES.value['embodied_energy']?.[c.category] ??
      '#B8CCEC',
  })),
);
</script>

<template>
  <div>
    <div>
      <q-card flat>
        <div ref="additionalGridRef" class="additional-grid">
          <!-- ═══ HEADCOUNT SECTION ═══ -->
          <!-- Headcount not validated: full-width placeholder -->
          <div
            v-if="!headcountValidated"
            class="additional-col additional-placeholder additional-placeholder--wide"
          >
            <div class="placeholder-content">
              <q-icon name="o_info" size="md" color="negative" />
              <div class="text-subtitle1 text-weight-medium q-mt-sm">
                {{ $t('results_additional_validate_headcount_title') }}
              </div>
              <div class="text-body2 text-secondary q-mt-xs">
                {{ $t('results_additional_validate_headcount_message') }}
              </div>
            </div>
          </div>

          <!-- Headcount validated but no data: placeholder -->
          <div
            v-else-if="headcountHasNoData"
            class="additional-col additional-placeholder additional-placeholder--wide"
          >
            <div class="placeholder-content">
              <q-icon name="o_info" size="md" color="negative" />
              <div class="text-subtitle1 text-weight-medium q-mt-sm">
                {{ $t('results_additional_headcount_no_data_title') }}
              </div>
              <div class="text-body2 text-secondary q-mt-xs">
                {{ $t('results_additional_headcount_no_data_message') }}
              </div>
            </div>
          </div>

          <!-- Headcount validated with data: 3 category columns -->
          <template v-else>
            <!-- Column 1: commuting -->
            <div class="additional-col">
              <div class="q-pt-xl q-px-lg additional-header">
                <div class="text-h5 text-weight-medium text-center">
                  {{ $t('charts-commuting-category') }}
                </div>
                <div class="text-caption text-secondary q-mt-xs text-center">
                  {{ $t('results_additional_commuting_breakdown_title') }}
                </div>
              </div>
              <q-separator class="q-my-lg" />
              <div>
                <div class="total-value items-center">
                  <div
                    class="text-h1 text-weight-medium"
                    :style="{ color: getCategoryAccent('commuting') }"
                  >
                    {{ $formatTonnesCO2(commutingTotal) }}
                  </div>
                  <div class="total-unit text-secondary text-body2">
                    {{ $t('results_units_tonnes') }}
                  </div>
                </div>
              </div>
              <q-separator class="q-my-lg" />
              <div
                v-if="commutingEntries.length"
                class="q-pt-md q-pb-xl q-px-md"
              >
                <div class="text-overline text-secondary text-center q-mb-xs">
                  {{ $t('results_additional_co2_chart_title_percent') }}
                </div>
                <VChart
                  v-if="chartsInView"
                  :key="`commuting-co2-${commutingEntries.length}`"
                  :option="commutingCO2Option"
                  :autoresize="chartsInView"
                  class="chart"
                />
                <q-skeleton v-else type="rect" class="chart" />
                <div
                  class="text-overline text-secondary text-center q-mt-md q-mb-xs"
                >
                  {{
                    $t(
                      'results_additional_commuting_physical_chart_title_percent',
                    )
                  }}
                </div>
                <VChart
                  v-if="chartsInView"
                  :key="`commuting-qty-${commutingEntries.length}`"
                  :option="commutingPhysicalOption"
                  :autoresize="chartsInView"
                  class="chart"
                />
                <q-skeleton v-else type="rect" class="chart" />
                <div
                  class="q-mt-md flex flex-wrap justify-center q-gutter-x-md q-gutter-y-xs"
                >
                  <div
                    v-for="item in commutingLegend"
                    :key="item.key"
                    class="flex items-center"
                  >
                    <div
                      class="legend-dot q-mr-xs"
                      :style="{ backgroundColor: item.color }"
                    />
                    <span class="text-caption">{{ item.label }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="q-pt-md q-pb-md q-px-md">
                <div class="text-body2 text-secondary">
                  {{ $t('no-chart-data') }}
                </div>
              </div>
            </div>

            <!-- Column 2: food -->
            <div class="additional-col">
              <div class="q-pt-xl q-px-lg additional-header">
                <div class="text-h5 text-weight-medium text-center">
                  {{ $t('charts-food-category') }}
                </div>
                <div class="text-caption text-secondary q-mt-xs text-center">
                  {{ $t('results_additional_food_breakdown_title') }}
                </div>
              </div>
              <q-separator class="q-my-lg" />
              <div>
                <div class="total-value items-center">
                  <div
                    class="text-h1 text-weight-medium"
                    :style="{ color: getCategoryAccent('food') }"
                  >
                    {{ $formatTonnesCO2(foodTotal) }}
                  </div>
                  <div class="total-unit text-secondary text-body2">
                    {{ $t('results_units_tonnes') }}
                  </div>
                </div>
              </div>
              <q-separator class="q-my-lg" />
              <div v-if="foodEntries.length" class="q-pt-md q-pb-xl q-px-md">
                <div class="text-overline text-secondary text-center q-mb-xs">
                  {{ $t('results_additional_co2_chart_title_percent') }}
                </div>
                <VChart
                  v-if="chartsInView"
                  :option="foodCO2Option"
                  :autoresize="chartsInView"
                  class="chart"
                />
                <q-skeleton v-else type="rect" class="chart" />
                <div
                  class="text-overline text-secondary text-center q-mt-md q-mb-xs"
                >
                  {{
                    $t('results_additional_food_physical_chart_title_percent')
                  }}
                </div>
                <VChart
                  v-if="chartsInView"
                  :option="foodPhysicalOption"
                  :autoresize="chartsInView"
                  class="chart"
                />
                <q-skeleton v-else type="rect" class="chart" />
                <div
                  class="q-mt-md flex flex-wrap justify-center q-gutter-x-md q-gutter-y-xs"
                >
                  <div
                    v-for="item in foodLegend"
                    :key="item.key"
                    class="flex items-center"
                  >
                    <div
                      class="legend-dot q-mr-xs"
                      :style="{ backgroundColor: item.color }"
                    />
                    <span class="text-caption">{{ item.label }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="q-pt-md q-pb-md q-px-md">
                <div class="text-body2 text-secondary">
                  {{ $t('no-chart-data') }}
                </div>
              </div>
            </div>

            <!-- Column 3: waste -->
            <div class="additional-col">
              <div class="q-pt-xl q-px-lg additional-header">
                <div class="text-h5 text-weight-medium text-center">
                  {{ $t('charts-waste-category') }}
                  <q-icon name="o_info" size="xs" class="q-ml-xs text-primary">
                    <q-tooltip class="text-body2 text-black">
                      {{ $t('results_additional_waste_tooltip') }}
                    </q-tooltip>
                  </q-icon>
                </div>
                <div class="text-caption text-secondary q-mt-xs text-center">
                  {{ $t('results_additional_waste_breakdown_title') }}
                </div>
              </div>
              <q-separator class="q-my-lg" />
              <div>
                <div class="total-value items-center">
                  <div
                    class="text-h1 text-weight-medium"
                    :style="{ color: getCategoryAccent('waste') }"
                  >
                    {{ $formatTonnesCO2(wasteTotal) }}
                  </div>
                  <div class="total-unit text-secondary text-body2">
                    {{ $t('results_units_tonnes') }}
                  </div>
                </div>
              </div>
              <q-separator class="q-my-lg" />
              <div v-if="wasteGrouped.length" class="q-pt-md q-pb-xl q-px-md">
                <div class="text-overline text-secondary text-center q-mb-xs">
                  {{ $t('results_additional_co2_chart_title_percent') }}
                </div>
                <VChart
                  v-if="chartsInView"
                  :option="wasteCO2Option"
                  :autoresize="chartsInView"
                  class="chart"
                />
                <q-skeleton v-else type="rect" class="chart" />
                <div
                  class="text-overline text-secondary text-center q-mt-md q-mb-xs"
                >
                  {{
                    $t('results_additional_waste_physical_chart_title_percent')
                  }}
                </div>
                <VChart
                  v-if="chartsInView"
                  :option="wastePhysicalOption"
                  :autoresize="chartsInView"
                  class="chart"
                />
                <q-skeleton v-else type="rect" class="chart" />
                <div
                  class="q-mt-md flex flex-wrap justify-center q-gutter-x-md q-gutter-y-xs"
                >
                  <div
                    v-for="item in wasteLegend"
                    :key="item.key"
                    class="flex items-center"
                  >
                    <div
                      class="legend-dot q-mr-xs"
                      :style="{ backgroundColor: item.color }"
                    />
                    <span class="text-caption">{{ item.label }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="q-pt-md q-pb-md q-px-md">
                <div class="text-body2 text-secondary">
                  {{ $t('no-chart-data') }}
                </div>
              </div>
            </div>
          </template>

          <!-- BUILDINGS SECTION  -->
          <!-- Buildings not validated: placeholder -->
          <div
            v-if="!buildingsValidated"
            class="additional-col additional-placeholder"
          >
            <div class="placeholder-content">
              <q-icon name="o_info" size="md" color="negative" />
              <div class="text-subtitle1 text-weight-medium q-mt-sm">
                {{ $t('results_additional_validate_buildings_title') }}
              </div>
              <div class="text-body2 text-secondary q-mt-xs">
                {{ $t('results_additional_validate_buildings_message') }}
              </div>
            </div>
          </div>

          <!-- Buildings validated but no data: placeholder -->
          <div
            v-else-if="embodiedEnergyTotal <= 0"
            class="additional-col additional-placeholder"
          >
            <div class="placeholder-content">
              <q-icon name="o_info" size="md" color="negative" />
              <div class="text-subtitle1 text-weight-medium q-mt-sm">
                {{ $t('results_additional_buildings_no_data_title') }}
              </div>
              <div class="text-body2 text-secondary q-mt-xs">
                {{ $t('results_additional_buildings_no_data_message') }}
              </div>
            </div>
          </div>

          <!-- Buildings validated with data -->
          <div v-else class="additional-col">
            <div class="q-pt-xl q-px-lg additional-header">
              <div class="text-h5 text-weight-medium text-center">
                {{ $t('charts-embodied-energy-category') }}
                <q-icon name="o_info" size="xs" class="q-ml-xs text-primary">
                  <q-tooltip class="text-body2 text-black">
                    {{ $t('results_additional_embodied_energy_tooltip') }}
                  </q-tooltip>
                </q-icon>
              </div>
              <div class="text-caption text-secondary q-mt-xs text-center">
                {{ $t('results_additional_embodied_energy_breakdown_title') }}
              </div>
            </div>
            <q-separator class="q-my-lg" />
            <div>
              <div class="total-value items-center">
                <div
                  class="text-h1 text-weight-medium"
                  :style="{ color: getCategoryAccent('embodied_energy') }"
                >
                  {{ $formatTonnesCO2(embodiedEnergyTotal) }}
                </div>
                <div class="total-unit text-secondary text-body2">
                  {{ $t('results_units_tonnes') }}
                </div>
              </div>
            </div>
            <q-separator class="q-my-lg" />
            <div
              v-if="embodiedEnergyByCategoryData.length"
              class="q-pt-md q-pb-xl q-px-md"
            >
              <div class="text-overline text-secondary text-center q-mb-xs">
                {{ $t('results_additional_co2_chart_title_percent') }}
              </div>
              <VChart
                v-if="chartsInView"
                :option="embodiedEnergyCO2Option"
                :autoresize="chartsInView"
                class="chart"
              />
              <q-skeleton v-else type="rect" class="chart" />
              <div
                class="q-mt-md flex flex-wrap justify-center q-gutter-x-md q-gutter-y-xs"
              >
                <div
                  v-for="item in embodiedEnergyLegend"
                  :key="item.key"
                  class="flex items-center"
                >
                  <div
                    class="legend-dot q-mr-xs"
                    :style="{ backgroundColor: item.color }"
                  />
                  <span class="text-caption">{{ item.label }}</span>
                </div>
              </div>
              <div
                class="text-caption text-secondary q-mt-md text-center text-italic"
              >
                {{ $t('results_additional_embodied_energy_chart_tooltip') }}
              </div>
            </div>
            <div v-else class="q-pt-md q-pb-md q-px-md">
              <div class="text-body2 text-secondary">
                {{ $t('no-chart-data') }}
              </div>
            </div>
          </div>
        </div>
      </q-card>
    </div>
  </div>
</template>

<style scoped>
.additional-grid {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
}

@media (min-width: 1024px) {
  .additional-grid {
    flex-direction: row;
  }
}

.additional-col {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  flex: 1 1 0%;
  min-height: 700px;
}

@media (max-width: 1023px) {
  .additional-col:not(:last-child) {
    border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  }
}

@media (min-width: 1024px) {
  .additional-col:not(:last-child) {
    border-right: 1px solid rgba(0, 0, 0, 0.12);
  }
}

.additional-header {
  min-height: 100px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.chart {
  height: 200px;
  width: 100%;
}

@media (min-width: 1024px) {
  .chart {
    height: 260px;
  }
}

.total-value {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-wrap: wrap;
}

.total-unit {
  line-height: 1;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

.additional-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
}

.additional-placeholder--wide {
  flex: 3 1 0%;
}

.placeholder-content {
  text-align: center;
  max-width: 400px;
  padding: 48px 24px;
}
</style>
