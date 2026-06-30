<script setup lang="ts">
import { computed, ref, watch, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { useModuleStore } from 'src/stores/modules';
import type { CompareYearsResponse } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import {
  RESULTS_CATEGORY_ORDER,
  RESULTS_CATEGORY_LABEL_KEYS,
  CHART_CATEGORY_COLOR_SCHEMES,
} from 'src/constant/charts';
import {
  defaultSelectedYears,
  presentCategories,
  computeCompareYearsTotal,
  computeCompareYearsObjective,
  type CompareYearsObjective,
} from 'src/utils/compareYears';
import { nOrDash } from 'src/utils/number';
import CompareYearsChart, {
  type CompareYearsSeries,
  type CompareYearsObjectiveBar,
} from './CompareYearsChart.vue';

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  unitId: {
    type: Number as PropType<number | null | undefined>,
    default: null,
  },
});

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const { t } = useI18n();
const moduleStore = useModuleStore();
const workspaceStore = useWorkspaceStore();
const yearConfigStore = useYearConfigStore();

function readCssVarHex(name: string): string | null {
  try {
    if (typeof window === 'undefined') return null;
    const v = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    return v || null;
  } catch {
    return null;
  }
}

// Quasar's `info` colour for the objective bar (distinct from the category palette).
const infoColorHex = ref<string | null>(null);

// Scope colours from the shared specification document.
const SCOPE_COLORS: Record<string, string> = {
  '1': '#E2E4F4',
  '2': '#D5D7EF',
  '3': '#C5CAE9',
};

const data = ref<CompareYearsResponse | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

const SCOPE_KEYS = ['1', '2', '3'] as const;

const selectedYears = ref<number[]>([]);
const selectedCategories = ref<string[]>([]);
const selectedScopes = ref<string[]>([...SCOPE_KEYS]);
// Toggle for the trailing objective bar in the by-category chart. Surfaced as
// an extra "Objective"/"Total" item at the bottom of the year & category lists.
const showObjective = ref(true);

async function load() {
  if (props.unitId == null) return;
  loading.value = true;
  error.value = null;
  infoColorHex.value = readCssVarHex('--q-info');
  try {
    const year = workspaceStore.selectedYear ?? new Date().getFullYear();
    const [res] = await Promise.all([
      moduleStore.getMultiYearBreakdown(props.unitId),
      // Populate reduction_objectives.goals for the objective bar.
      yearConfigStore.fetchConfig(year),
    ]);
    data.value = res;
    // Default selection: every year that actually has emissions, all
    // categories that appear in any year.
    selectedYears.value = defaultSelectedYears(res.years);
    selectedCategories.value = presentCategories(
      res.years,
      RESULTS_CATEGORY_ORDER,
    );
    selectedScopes.value = [...SCOPE_KEYS];
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'Unknown error';
    data.value = null;
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) void load();
  },
);

const yearOptions = computed(() =>
  (data.value?.years ?? []).map((y) => y.year),
);

const categoryOptions = computed(() =>
  presentCategories(data.value?.years ?? [], RESULTS_CATEGORY_ORDER).map(
    (key) => ({
      value: key,
      label: t(
        RESULTS_CATEGORY_LABEL_KEYS[
          key as keyof typeof RESULTS_CATEGORY_LABEL_KEYS
        ],
      ),
    }),
  ),
);

const sortedSelectedYears = computed(() =>
  [...selectedYears.value].sort((a, b) => a - b),
);

function categoryColor(key: string): string {
  return CHART_CATEGORY_COLOR_SCHEMES.value[
    key as keyof typeof CHART_CATEGORY_COLOR_SCHEMES.value
  ];
}

const scopeOptions = computed(() =>
  SCOPE_KEYS.map((scope) => ({
    value: scope,
    label: `${t('charts-scope')} ${scope}`,
  })),
);

const moduleSeries = computed<CompareYearsSeries[]>(() =>
  RESULTS_CATEGORY_ORDER.filter((key) =>
    selectedCategories.value.includes(key),
  ).map((key) => ({
    key,
    label: t(RESULTS_CATEGORY_LABEL_KEYS[key]),
    color: CHART_CATEGORY_COLOR_SCHEMES.value[key],
  })),
);

const scopeSeries = computed<CompareYearsSeries[]>(() =>
  SCOPE_KEYS.filter((scope) => selectedScopes.value.includes(scope)).map(
    (scope) => ({
      key: scope,
      label: `${t('charts-scope')} ${scope}`,
      color: SCOPE_COLORS[scope],
    }),
  ),
);

const moduleDataByYear = computed<Record<number, Record<string, number>>>(
  () => {
    const map: Record<number, Record<string, number>> = {};
    for (const entry of data.value?.years ?? []) {
      map[entry.year] = entry.modules;
    }
    return map;
  },
);

const scopeDataByYear = computed<Record<number, Record<string, number>>>(() => {
  const map: Record<number, Record<string, number>> = {};
  for (const entry of data.value?.years ?? []) {
    map[entry.year] = entry.scopes;
  }
  return map;
});

// Total reflects the active selection: selected years × selected categories.
const totalTonnes = computed(() =>
  computeCompareYearsTotal(
    data.value?.years ?? [],
    selectedYears.value,
    selectedCategories.value,
  ),
);

const hasData = computed(() => (data.value?.years.length ?? 0) > 0);

// Compact "YYYY–YYYY" (or single year) label for the KPI band.
const yearRangeLabel = computed(() => {
  const years = sortedSelectedYears.value;
  if (years.length === 0) return '';
  const first = years[0];
  const last = years[years.length - 1];
  return first === last ? String(first) : `${first}–${last}`;
});

function formatTonnes(value: number): string {
  return nOrDash(value, {
    options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
  });
}

// Latest reduction goal applied to the latest selected year's
// selected-category total. Shared by the KPI band and the chart bar.
const objective = computed<CompareYearsObjective | null>(() => {
  const goals =
    yearConfigStore.config?.config?.reduction_objectives?.goals ?? [];
  return computeCompareYearsObjective(
    data.value?.years ?? [],
    selectedYears.value,
    selectedCategories.value,
    goals,
  );
});

// KPI: how far the latest selected year sits above/below its objective.
const objectiveGap = computed(() => {
  const obj = objective.value;
  if (!obj || obj.valueTonnes <= 0 || selectedYears.value.length === 0) {
    return null;
  }
  const latestTonnes = computeCompareYearsTotal(
    data.value?.years ?? [],
    [Math.max(...selectedYears.value)],
    selectedCategories.value,
  );
  return {
    targetYear: obj.targetYear,
    objectiveTonnes: obj.valueTonnes,
    pct: (latestTonnes - obj.valueTonnes) / obj.valueTonnes,
  };
});

const objectiveBar = computed<CompareYearsObjectiveBar | null>(() => {
  if (!showObjective.value) return null;
  const obj = objective.value;
  if (!obj) return null;
  return {
    label: t('results_compare_years_objective_tick', {
      year: obj.targetYear,
    }),
    value: obj.valueTonnes,
    color: infoColorHex.value ?? '#1976d2',
  };
});
</script>

<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <q-card class="compare-years-dialog">
      <q-card-section class="row items-center q-pb-none">
        <div class="text-h4 text-weight-medium">
          {{ $t('results_compare_years_title') }}
        </div>
        <q-space />
        <q-btn v-close-popup flat round dense icon="o_close" color="grey-6" />
      </q-card-section>

      <q-separator class="q-mt-sm" />

      <q-card-section v-if="loading" class="flex justify-center q-py-xl">
        <q-spinner color="info" size="2rem" />
      </q-card-section>

      <q-card-section v-else-if="error" class="text-negative">
        {{ error }}
      </q-card-section>

      <q-card-section v-else-if="!hasData" class="text-secondary">
        {{ $t('results_compare_years_no_data') }}
      </q-card-section>

      <template v-else>
        <q-card-section class="q-py-none">
          <div class="compare-years-kpis">
            <!-- Total for the active year × category selection -->
            <div class="compare-years-kpi">
              <div class="compare-years-kpi__label">
                {{ $t('results_compare_years_total') }} · {{ yearRangeLabel }}
              </div>
              <div class="compare-years-kpi__value">
                {{ formatTonnes(totalTonnes) }}
                <span class="compare-years-kpi__unit">
                  {{ $t('results_units_tonnes') }}
                </span>
              </div>
            </div>

            <q-separator
              v-if="objectiveGap"
              vertical
              class="compare-years-kpi__divider"
            />

            <!-- Gap of the latest selected year to its reduction objective -->
            <div v-if="objectiveGap" class="compare-years-kpi">
              <div class="compare-years-kpi__label">
                {{
                  $t('results_compare_years_gap_label', {
                    year: objectiveGap.targetYear,
                  })
                }}
              </div>
              <div class="compare-years-kpi__gap">
                <span
                  class="compare-years-kpi__delta"
                  :class="objectiveGap.pct > 0 ? 'text-negative' : 'text-info'"
                >
                  {{ objectiveGap.pct > 0 ? '+' : ''
                  }}{{
                    $nOrDash(objectiveGap.pct * 100, {
                      options: { maximumFractionDigits: 0 },
                    })
                  }}%
                </span>
                <span class="compare-years-kpi__sub">
                  {{
                    $t('results_compare_years_gap_target', {
                      value: `${formatTonnes(objectiveGap.objectiveTonnes)} ${$t(
                        'results_units_tonnes',
                      )}`,
                    })
                  }}
                </span>
              </div>
            </div>

            <q-separator
              v-if="objectiveGap"
              vertical
              class="compare-years-kpi__divider"
            />

            <q-space />

            <!-- Global years filter -->
            <q-select
              v-model="selectedYears"
              :options="yearOptions"
              :label="$t('results_compare_years_filter_years')"
              class="compare-years-kpi__years"
              multiple
              outlined
              dense
              options-dense
            >
              <template #selected>
                {{ sortedSelectedYears.join(', ') }}
              </template>
              <template #option="{ itemProps, opt, selected, toggleOption }">
                <q-item v-bind="itemProps">
                  <q-item-section side>
                    <q-checkbox
                      :model-value="selected"
                      size="sm"
                      color="info"
                      @update:model-value="toggleOption(opt)"
                    />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label>{{ opt }}</q-item-label>
                  </q-item-section>
                </q-item>
              </template>
              <template #after-options>
                <q-item v-ripple clickable @click="showObjective = !showObjective">
                  <q-item-section side>
                    <q-checkbox
                      v-model="showObjective"
                      size="sm"
                      class="compare-years-category-checkbox"
                      :style="{ color: 'var(--q-info)' }"
                    />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label>
                      {{ $t('results_compare_years_objective_option') }}
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </template>
            </q-select>
          </div>
        </q-card-section>

        <q-separator />

        <q-card-section>
          <div class="row items-end justify-between q-col-gutter-md q-mb-sm">
            <div class="col-12 col-sm">
              <div class="text-body1 text-weight-medium">
                {{ $t('results_compare_years_by_module') }}
                <span class="text-caption text-secondary">
                  ({{ $t('results_units_tonnes') }})
                </span>
              </div>
            </div>
            <div class="col-12 col-sm-3">
              <q-select
                v-model="selectedCategories"
                :options="categoryOptions"
                :label="$t('results_compare_years_filter_modules')"
                multiple
                emit-value
                map-options
                outlined
                dense
                options-dense
              >
                <template #selected>
                  {{
                    $t('results_compare_years_selected_count', {
                      count: selectedCategories.length,
                    })
                  }}
                </template>
                <template #option="{ itemProps, opt, selected, toggleOption }">
                  <q-item v-bind="itemProps">
                    <q-item-section side>
                      <q-checkbox
                        :model-value="selected"
                        size="sm"
                        class="compare-years-category-checkbox"
                        :style="{ color: categoryColor(opt.value) }"
                        @update:model-value="toggleOption(opt)"
                      />
                    </q-item-section>
                    <q-item-section>
                      <q-item-label>{{ opt.label }}</q-item-label>
                    </q-item-section>
                  </q-item>
                </template>
                <template #after-options>
                  <q-item
                    v-ripple
                    clickable
                    @click="showObjective = !showObjective"
                  >
                    <q-item-section side>
                      <q-checkbox
                        v-model="showObjective"
                        size="sm"
                        class="compare-years-category-checkbox"
                        :style="{ color: 'var(--q-info)' }"
                      />
                    </q-item-section>
                    <q-item-section>
                      <q-item-label>
                        {{ $t('results_compare_years_total') }}
                      </q-item-label>
                    </q-item-section>
                  </q-item>
                </template>
              </q-select>
            </div>
          </div>
          <div class="compare-years-chart-box">
            <CompareYearsChart
              :years="sortedSelectedYears"
              :series="moduleSeries"
              :data-by-year="moduleDataByYear"
              :objective="objectiveBar"
            />
          </div>
        </q-card-section>

        <q-separator />

        <q-card-section>
          <div class="row items-end justify-between q-col-gutter-md q-mb-sm">
            <div class="col-12 col-sm">
              <div class="text-body1 text-weight-medium">
                {{ $t('results_compare_years_by_scope') }}
                <span class="text-caption text-secondary">
                  ({{ $t('results_units_tonnes') }})
                </span>
              </div>
            </div>
            <div class="col-12 col-sm-3">
              <q-select
                v-model="selectedScopes"
                :options="scopeOptions"
                :label="$t('results_compare_years_filter_scopes')"
                multiple
                emit-value
                map-options
                outlined
                dense
                options-dense
              >
                <template #selected>
                  {{
                    $t('results_compare_years_selected_count', {
                      count: selectedScopes.length,
                    })
                  }}
                </template>
                <template #option="{ itemProps, opt, selected, toggleOption }">
                  <q-item v-bind="itemProps">
                    <q-item-section side>
                      <q-checkbox
                        :model-value="selected"
                        size="sm"
                        class="compare-years-category-checkbox"
                        :style="{ color: SCOPE_COLORS[opt.value] }"
                        @update:model-value="toggleOption(opt)"
                      />
                    </q-item-section>
                    <q-item-section>
                      <q-item-label>{{ opt.label }}</q-item-label>
                    </q-item-section>
                  </q-item>
                </template>
              </q-select>
            </div>
          </div>
          <div class="compare-years-chart-box">
            <CompareYearsChart
              :years="sortedSelectedYears"
              :series="scopeSeries"
              :data-by-year="scopeDataByYear"
            />
          </div>
        </q-card-section>
      </template>
    </q-card>
  </q-dialog>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.compare-years-dialog {
  width: 100%;
  max-width: tokens.$modal-width-lg;
  max-height: 90vh;
}

/* Roomier outer margins around the dialog content. */
.compare-years-dialog :deep(.q-card-section) {
  padding-left: tokens.$spacing-xxl;
  padding-right: tokens.$spacing-xxl;
}

/* Compact KPI band: total + objective gap on the left, years filter right. */
.compare-years-kpis {
  display: flex;
  align-items: stretch;
  gap: 40px;
  flex-wrap: wrap;
}

/* Padding lives on the KPI items (not the band) so the vertical separators,
   which are bare flex children, stretch the full height and touch top/bottom. */
.compare-years-kpi {
  padding: tokens.$spacing-lg 0;
}

.compare-years-kpi__label {
  letter-spacing: 0.06em;
  font-size: 11px;
  color: var(--semantic-color-text-muted);
  margin-bottom: tokens.$spacing-xs;
}

.compare-years-kpi__value {
  font-size: 26px;
  line-height: 1.1;
  color: var(--semantic-color-text);
}

.compare-years-kpi__unit {
  font-size: 13px;
  font-weight: tokens.$text-weight-regular;
  color: var(--semantic-color-text-muted);
}

.compare-years-kpi__gap {
  display: flex;
  align-items: baseline;
  gap: tokens.$spacing-sm;
}

.compare-years-kpi__delta {
  font-size: 22px;
  line-height: 1.1;
}

.compare-years-kpi__sub {
  font-size: 13px;
  color: var(--semantic-color-text-muted);
}

.compare-years-kpi__divider {
  height: auto;
  align-self: stretch;
}

/* Years filter sits as a compact pill on the right of the KPI band. */
.compare-years-kpi__years {
  width: 180px;
  max-width: 100%;
  align-self: center;
}

/* Breathing room around each chart inside its section. */
.compare-years-chart-box {
  padding: tokens.$spacing-sm tokens.$spacing-sm 0;
}

/* Tint each category checkbox with its chart colour (set via inline `color`)
   so the legend-less charts stay readable from the filter. */
.compare-years-category-checkbox :deep(.q-checkbox__inner) {
  color: inherit;
}
</style>
