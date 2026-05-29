<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  h,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
} from 'vue';
import { QSkeleton } from 'quasar';
import { MODULES_LIST, MODULES, type Module } from 'src/constant/modules';
import ModuleIconBox from 'src/components/atoms/ModuleIconBox.vue';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import { getModuleIconColors } from 'src/composables/useModuleIconColors';
import {
  getResultsSummary,
  type ResultsSummary,
  type ModuleResult,
} from 'src/api/modules';

import { useWorkspaceStore } from 'src/stores/workspace';
import { useTimelineStore, useModuleStore } from 'src/stores/modules';
import { useResultsFiltersStore } from 'src/stores/resultsFilters';
import { storeToRefs } from 'pinia';
import { IT_FOCUS_SOURCE_MODULES } from 'src/constant/itFocus';
import { MODULE_STATES, getModuleTypeId } from 'src/constant/moduleStates';
import { useI18n } from 'vue-i18n';
import { useYearConfigStore } from 'src/stores/yearConfig';
import ReductionObjectiveChart from 'src/components/charts/results/ReductionObjectiveChart.vue';
import ResultsFilterPill from 'src/components/layout/ResultsFilterPill.vue';
import { useRoute, useRouter } from 'vue-router';
import { nOrDash } from 'src/utils/number';

const yearConfigStore = useYearConfigStore();

/** Keeps ECharts-heavy bundles out of the initial Results route chunk (Lighthouse / TTI). */
const ChartChunkSkeleton = () =>
  h(QSkeleton, {
    type: 'rect',
    height: '360px',
    class: 'full-width q-ma-sm',
  });

const ModuleCarbonFootprintChart = defineAsyncComponent({
  loader: () =>
    import('src/components/charts/results/ModuleCarbonFootprintChart.vue'),
  loadingComponent: ChartChunkSkeleton,
  delay: 0,
});

const CarbonFootPrintPerPersonChart = defineAsyncComponent({
  loader: () =>
    import('src/components/charts/results/CarbonFootPrintPerPersonChart.vue'),
  loadingComponent: ChartChunkSkeleton,
  delay: 0,
});

const ModuleCharts = defineAsyncComponent({
  loader: () => import('src/components/organisms/module/ModuleCharts.vue'),
  loadingComponent: ChartChunkSkeleton,
  delay: 0,
});

const AdditionalSectionSkeleton = () =>
  h(QSkeleton, {
    type: 'rect',
    height: '560px',
    class: 'full-width q-ma-md',
  });

const AdditionalCategoriesSection = defineAsyncComponent({
  loader: () =>
    import('src/components/organisms/AdditionalCategoriesSection.vue'),
  loadingComponent: AdditionalSectionSkeleton,
  delay: 0,
});

const ItFocusSection = defineAsyncComponent({
  loader: () => import('src/components/organisms/ItFocusSection.vue'),
  loadingComponent: AdditionalSectionSkeleton,
  delay: 0,
});

/** Per-row expansion; body mounts only when opened (avoids N× chart bundles on load). */
const resultsCategoryExpanded = reactive(
  Object.fromEntries(MODULES_LIST.map((m) => [m, false])) as Record<
    string,
    boolean
  >,
);

const FORMAT_INTEGER = {
  options: { minimumFractionDigits: 0, maximumFractionDigits: 0 },
};
const FORMAT_CO2_PER_KM = {
  options: { minimumFractionDigits: 2, maximumFractionDigits: 2 },
};

const co2PerKmKg = computed(() => resultsSummary.value?.co2_per_km_kg ?? 0);
const hasCo2PerKmKg = computed(() => co2PerKmKg.value > 0);

const percentChangeFormatter = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: 'always',
});

const perPersonBreakdown = computed(
  () => moduleStore.state.emissionBreakdown?.per_person_breakdown ?? null,
);

const validatedCategories = computed(
  () => moduleStore.state.emissionBreakdown?.validated_categories ?? null,
);

const headcountValidatedForPerPerson = computed(() => {
  return validatedCategories.value?.includes('commuting') ?? false;
});

function formatPercentChange(value: number | null | undefined): string {
  if (value == null) return '-';
  return percentChangeFormatter.format(value / 100);
}

const workspaceStore = useWorkspaceStore();
const timelineStore = useTimelineStore();
const moduleStore = useModuleStore();
const resultsFiltersStore = useResultsFiltersStore();
const { hideResearchFacilities, hideAdditionalData } =
  storeToRefs(resultsFiltersStore);
const router = useRouter();
const route = useRoute();
const currentYear = computed(() => {
  return workspaceStore.selectedYear ?? new Date().getFullYear();
});

const resultsSummary = ref<ResultsSummary | null>(null);
const resultsSummaryLoading = ref(true);

const mountPrimaryCharts = ref(false);
const mountBelowFold = ref(false);

const excludedModules = computed(() => {
  const ids: number[] = [];
  if (hideResearchFacilities.value) {
    const id = getModuleTypeId(MODULES.ResearchFacilities);
    if (id !== undefined) ids.push(id);
  }
  return ids;
});

async function fetchResultsSummary() {
  const carbonReportId = workspaceStore.selectedCarbonReport?.id;
  if (!carbonReportId) return;

  try {
    resultsSummaryLoading.value = true;
    resultsSummary.value = await getResultsSummary(
      carbonReportId,
      excludedModules.value,
    );
  } catch {
    resultsSummary.value = null;
  } finally {
    resultsSummaryLoading.value = false;
  }
}

async function fetchEmissionBreakdown() {
  const carbonReportId = workspaceStore.selectedCarbonReport?.id;
  if (!carbonReportId) return;
  await moduleStore.getEmissionBreakdown(carbonReportId, excludedModules.value);
}

async function fetchItBreakdown() {
  const carbonReportId = workspaceStore.selectedCarbonReport?.id;
  if (!carbonReportId) return;
  await moduleStore.getItBreakdown(carbonReportId, excludedModules.value);
}

/** Schedule a callback after the next paint frame, then wait for idle. */
function afterPaint(cb: () => void) {
  requestAnimationFrame(() => {
    // Double rAF ensures one full frame has painted before scheduling idle work.
    requestAnimationFrame(() => {
      const idle =
        window.requestIdleCallback ??
        ((fn: () => void) => window.setTimeout(fn, 80));
      idle(cb);
    });
  });
}

onMounted(async () => {
  await fetchResultsSummary();

  // Phase 1: after first paint, mount charts + start data fetches.
  afterPaint(async () => {
    mountPrimaryCharts.value = true;
    await fetchEmissionBreakdown();
    await fetchItBreakdown();
  });

  // Phase 2: below-fold sections after charts have started.
  afterPaint(async () => {
    mountBelowFold.value = true;
    await loadModulesConfig();
  });
});

// Watch for year/unit changes
watch(
  () => [
    workspaceStore.selectedCarbonReport?.id,
    currentYear.value,
    hideResearchFacilities.value,
  ],
  async () => {
    moduleStore.invalidateEmissionBreakdown();
    await fetchResultsSummary();
    afterPaint(async () => {
      await fetchEmissionBreakdown();
      await fetchItBreakdown();
    });
  },
);

const isModuleValidated = (module: string) => {
  return timelineStore.itemStates[module as Module] === MODULE_STATES.Validated;
};

const showItFocusSection = computed(() =>
  IT_FOCUS_SOURCE_MODULES.some(
    (m) => timelineStore.itemStates[m] === MODULE_STATES.Validated,
  ),
);

/**
 * Get the module result for a given frontend module key.
 * Returns the matching entry from module_results by module_type_id, or undefined.
 */
const getModuleResult = (module: string): ModuleResult | undefined => {
  if (!resultsSummary.value) return undefined;
  const typeId = getModuleTypeId(module as Module);
  return resultsSummary.value.module_results.find(
    (m) => m.module_type_id === typeId,
  );
};
const { t, te } = useI18n();

function getTotalModuleCarbonFootprintTitle(module: Module): string {
  const specificKey = `results_total_module_carbon_footprint_${module}`;
  if (te(specificKey)) return t(specificKey);
  return t('results_total_module_carbon_footprint', { module: t(module) });
}

onUnmounted(() => resultsFiltersStore.reset());

const totalCarComparison = computed(() => {
  if (!hasCo2PerKmKg.value || !resultsSummary.value) return undefined;
  return t('results_equivalent_to_car', {
    km: nOrDash(resultsSummary.value.unit_totals.equivalent_car_km, {
      options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
    }),
    value: nOrDash(co2PerKmKg.value, {
      options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
    }),
  });
});

const yearComparisonPct = computed(
  () => resultsSummary.value?.unit_totals.year_comparison_percentage ?? null,
);

const yearComparisonUnit = computed(() => {
  if (yearComparisonPct.value == null)
    return t('results_no_comparison_year_available');
  return t('results_compared_to', { year: (currentYear.value - 1).toString() });
});

const yearComparisonColor = computed(() => {
  if (yearComparisonPct.value == null) return undefined;
  return yearComparisonPct.value < 0 ? 'positive' : 'negative';
});

const yearComparisonText = computed(() => {
  if (yearComparisonPct.value == null || !resultsSummary.value)
    return undefined;
  return t('results_compared_to_value_of', {
    value: `${nOrDash(
      resultsSummary.value.unit_totals.previous_year_total_tonnes_co2eq,
      { options: { minimumFractionDigits: 1, maximumFractionDigits: 1 } },
    )}${t('results_units_tonnes')}`,
  });
});

const yearComparisonHighlight = computed(() => {
  if (yearComparisonPct.value == null || !resultsSummary.value)
    return undefined;
  return `${nOrDash(
    resultsSummary.value.unit_totals.previous_year_total_tonnes_co2eq,
    { options: { minimumFractionDigits: 1, maximumFractionDigits: 1 } },
  )}${t('results_units_tonnes')}`;
});

const fteBigNumberTitle = computed(() => {
  const fte = resultsSummary.value?.unit_totals.total_fte;
  if (fte == null) return t('results_carbon_footprint_per_FTE_no_headcount');
  return t('results_carbon_footprint_per_fte', {
    FTE: nOrDash(fte, { options: { maximumFractionDigits: 1 } }),
  });
});

function getModuleCarComparison(module: string): string | undefined {
  if (!hasCo2PerKmKg.value) return undefined;
  const result = getModuleResult(module);
  if (!result) return undefined;
  return t('results_equivalent_to_car', {
    km: nOrDash(result.equivalent_car_km, FORMAT_INTEGER),
    value: nOrDash(co2PerKmKg.value, FORMAT_CO2_PER_KM),
  });
}

const viewUncertainties = ref(false);
const viewAdditionalData = computed(() => !hideAdditionalData.value);
const compareYears = ref(false);

const additionalBreakdown = computed(
  () => moduleStore.state.emissionBreakdown?.additional_breakdown ?? [],
);
const commutingRow = computed(
  () =>
    additionalBreakdown.value.find((r) => r.category_key === 'commuting') ??
    null,
);
const foodRow = computed(
  () =>
    additionalBreakdown.value.find((r) => r.category_key === 'food') ?? null,
);
const wasteRow = computed(
  () =>
    additionalBreakdown.value.find((r) => r.category_key === 'waste') ?? null,
);
const embodiedEnergyRow = computed(
  () =>
    additionalBreakdown.value.find(
      (r) => r.category_key === 'embodied_energy',
    ) ?? null,
);
const embodiedEnergyByCategory = computed(
  () => moduleStore.state.emissionBreakdown?.embodied_energy_by_category ?? [],
);

// When additional data is hidden, subtract only the validated additional
// category totals from the results summary.  Unvalidated categories are
// not included in the results summary total, so must not be subtracted.
const validatedAdditionalTonnes = computed(() => {
  const validated = new Set(
    moduleStore.state.emissionBreakdown?.validated_categories ?? [],
  );
  return additionalBreakdown.value.reduce((sum, row) => {
    if (!validated.has(row.category_key)) return sum;
    const catTotal = row.emissions.reduce((categorySum, emission) => {
      return (
        categorySum + (typeof emission.value === 'number' ? emission.value : 0)
      );
    }, 0);
    return sum + catTotal;
  }, 0);
});

const adjustedTotalTonnes = computed(() => {
  const raw = resultsSummary.value?.unit_totals.total_tonnes_co2eq;
  if (raw == null) return null;
  return viewAdditionalData.value ? raw : raw - validatedAdditionalTonnes.value;
});

const adjustedTonnesPerFte = computed(() => {
  const fte = resultsSummary.value?.unit_totals.total_fte;
  if (adjustedTotalTonnes.value == null || !fte || fte <= 0) return null;
  return adjustedTotalTonnes.value / fte;
});

// Lazy-loaded: only used in below-fold expansion items
const modulesConfig = ref<Record<
  string,
  import('src/constant/moduleConfig').ModuleConfig
> | null>(null);
const loadModulesConfig = async () => {
  if (!modulesConfig.value) {
    const { MODULES_CONFIG } = await import('src/constant/module-config');
    modulesConfig.value = MODULES_CONFIG;
  }
};
const getModuleConfig = (module: string) => modulesConfig.value?.[module];

const downloadPDF = () => {
  const resolved = router.resolve({
    name: 'results-print',
    params: {
      language: String(route.params.language ?? 'en'),
      unit: workspaceStore.selectedParams?.unit ?? route.params.unit,
      year: String(currentYear.value),
    },
    query: {
      hideResearchFacilities: hideResearchFacilities.value ? '1' : '0',
      hideAdditionalData: hideAdditionalData.value ? '1' : '0',
    },
  });
  window.open(resolved.href, '_blank');
};

const getUncertainty = (
  uncertainty?: string,
): { color: string; label: string } => {
  switch (uncertainty) {
    case 'high':
      return { color: 'negative', label: t('uncertainty_high') };
    case 'medium':
      return { color: 'warning', label: t('uncertainty_medium') };
    case 'low':
      return { color: 'positive', label: t('uncertainty_low') };
    default:
      return { color: 'primary', label: '' };
  }
};
</script>

<template>
  <q-page>
    <ResultsFilterPill />
    <div class="page-grid">
      <q-card flat bordered class="q-pa-xl">
        <div class="flex justify-between items-center">
          <div>
            <h2 class="text-h2 text-weight-medium">
              {{ $t('results_title') }}
            </h2>
            <span class="text-body1 text-secondary">{{
              $t('results_subtitle', { year: currentYear })
            }}</span>
          </div>

          <div class="flex column justify-between">
            <q-btn
              color="info"
              icon="download"
              :label="$t('results_download_pdf')"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium q-mb-md"
              @click="downloadPDF"
            />
            <div class="flex column">
              <q-checkbox
                v-model="compareYears"
                :label="$t('results_compare_years')"
                color="info"
                class="text-weight-medium"
                size="xs"
              />
            </div>
          </div>
        </div>
      </q-card>
      <div class="summary-section">
        <q-card v-if="resultsSummary" flat bordered class="results-overview">
          <div class="results-summary-row results-overview__summary">
            <div class="results-summary-row__item">
              <BigNumber
                :title="$t('results_total_unit_carbon_footprint')"
                :number="
                  $nOrDash(adjustedTotalTonnes, {
                    options: {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    },
                  })
                "
                tooltip-placement="comparison"
                :comparison="totalCarComparison"
                :comparison-highlight="`${$nOrDash(
                  resultsSummary.unit_totals.equivalent_car_km,
                  {
                    options: {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    },
                  },
                )}km`"
                color="info"
                :bordered="false"
              >
                <template v-if="hasCo2PerKmKg" #tooltip>{{
                  $t('results_total_unit_carbon_footprint_tooltip', {
                    value: $nOrDash(co2PerKmKg, {
                      options: {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1,
                      },
                    }),
                    unit: $t('results_kg_co2eq_per_km'),
                  })
                }}</template>
              </BigNumber>
            </div>

            <q-separator vertical />

            <div
              class="results-summary-row__item"
              :class="{
                'no-data-styling':
                  resultsSummary.unit_totals.year_comparison_percentage == null,
              }"
            >
              <BigNumber
                :title="$t('results_unit_carbon_footprint')"
                :number="
                  formatPercentChange(
                    resultsSummary.unit_totals.year_comparison_percentage,
                  )
                "
                :unit="yearComparisonUnit"
                :color="yearComparisonColor"
                :comparison="yearComparisonText"
                :comparison-highlight="yearComparisonHighlight"
                :bordered="false"
              >
              </BigNumber>
            </div>

            <q-separator vertical />

            <div class="results-summary-row__item">
              <BigNumber
                :title="fteBigNumberTitle"
                :number="
                  $nOrDash(adjustedTonnesPerFte, {
                    options: {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    },
                  })
                "
                :comparison="
                  $t('results_paris_agreement_value', {
                    value: `${$nOrDash(2)}${$t('results_units_tonnes')}`,
                  })
                "
                :comparison-highlight="`${$nOrDash(2)}${$t('results_units_tonnes')}`"
                color="info"
                :bordered="false"
              >
              </BigNumber>
            </div>
          </div>

          <q-separator />

          <div class="results-charts-grid results-overview__charts">
            <div class="results-charts-grid__main">
              <template v-if="mountPrimaryCharts">
                <ModuleCarbonFootprintChart
                  :breakdown-data="moduleStore.state.emissionBreakdown"
                  :view-additional-data="viewAdditionalData"
                />
              </template>
              <q-skeleton
                v-else
                type="rect"
                height="360px"
                class="full-width"
              />
            </div>

            <q-separator
              vertical
              class="results-charts-grid__separator"
              aria-hidden="true"
            />

            <div class="results-charts-grid__side">
              <template v-if="!isModuleValidated(MODULES.Headcount)">
                <q-card flat bordered class="validation-required-card">
                  <q-card-section class="validation-required-card__content">
                    <q-icon
                      name="o_info"
                      size="md"
                      color="info"
                      class="q-mb-md"
                    />
                    <div class="text-h6 text-weight-medium text-center q-mb-sm">
                      {{
                        $t('results_validate_module_title', {
                          module: $t('headcount'),
                        })
                      }}
                    </div>
                    <div class="text-body2 text-secondary text-center">
                      {{ $t('results_validate_module_message') }}
                    </div>
                  </q-card-section>
                </q-card>
              </template>
              <template v-else>
                <template v-if="mountPrimaryCharts">
                  <CarbonFootPrintPerPersonChart
                    :per-person-breakdown="perPersonBreakdown"
                    :validated-categories="validatedCategories"
                    :headcount-validated="headcountValidatedForPerPerson"
                    :view-additional-data="viewAdditionalData"
                  />
                </template>
                <q-skeleton
                  v-else
                  type="rect"
                  height="360px"
                  class="full-width"
                />
              </template>
            </div>
          </div>
        </q-card>
        <q-card
          v-else-if="resultsSummaryLoading"
          flat
          class="grid-3-col results-summary-skeleton"
        >
          <q-skeleton
            v-for="n in 3"
            :key="n"
            type="rect"
            height="160px"
            class="full-width bg-white"
          />
        </q-card>
      </div>

      <!-- Reduction Objective -->
      <q-card v-if="mountBelowFold" flat bordered class="defer-render">
        <ReductionObjectiveChart
          :hide-research-facilities="hideResearchFacilities"
          :hide-additional-data="hideAdditionalData"
        />
      </q-card>

      <div v-if="mountBelowFold" class="defer-render sections-grid">
        <q-card bordered flat class="q-pa-none">
          <div class="flex justify-between items-center q-pa-xl q-pb-md">
            <div>
              <h2 class="text-h2 text-weight-medium">
                {{ $t('results_by_category_title') }}
              </h2>
              <span class="text-body1 text-secondary">{{
                $t('results_by_category_subtitle', {
                  year: currentYear,
                })
              }}</span>
            </div>
            <q-toggle
              v-model="viewUncertainties"
              :label="$t('results_view_uncertainties')"
              color="accent"
              keep-color
              size="lg"
              class="text-weight-medium"
            />
          </div>
          <!-- Module Collapse Items -->
          <template v-for="module in MODULES_LIST" :key="module">
            <template
              v-if="
                module !== MODULES.Headcount &&
                !(
                  hideResearchFacilities &&
                  module === MODULES.ResearchFacilities
                )
              "
            >
              <q-separator />
              <q-expansion-item
                v-model="resultsCategoryExpanded[module]"
                header-class="q-py-md"
              >
                <template #header>
                  <div class="flex justify-between items-center">
                    <ModuleIconBox :name="module" size="sm" class="q-mr-sm" />
                    <div class="text-h5 text-weight-medium">
                      {{ $t(module) }}
                    </div>
                    <q-badge
                      v-if="
                        viewUncertainties &&
                        !['none', null].includes(
                          yearConfigStore.getModuleUncertaintyTag(module),
                        )
                      "
                      outline
                      rounded
                      :color="
                        getUncertainty(
                          yearConfigStore.getModuleUncertaintyTag(module),
                        ).color
                      "
                      :label="
                        getUncertainty(
                          yearConfigStore.getModuleUncertaintyTag(module),
                        ).label
                      "
                      class="q-ml-sm"
                    />
                  </div>
                </template>
                <template v-if="resultsCategoryExpanded[module]">
                  <q-separator />

                  <div>
                    <!-- Module has results in the summary -->
                    <template v-if="getModuleResult(module)">
                      <!-- Per-module treemap -->
                      <template v-if="isModuleValidated(module)">
                        <ModuleCharts :type="module" />
                      </template>
                      <div class="module-stats-row">
                        <BigNumber
                          :title="
                            getTotalModuleCarbonFootprintTitle(module as Module)
                          "
                          :number="
                            getModuleConfig(module)?.totalFormatter(
                              getModuleResult(module)!.total_tonnes_co2eq,
                            )
                          "
                          :comparison="getModuleCarComparison(module)"
                          :comparison-highlight="`${$nOrDash(
                            getModuleResult(module)!.equivalent_car_km,
                            FORMAT_INTEGER,
                          )}km`"
                          :color-style="getModuleIconColors(module).iconColor"
                          :bordered="false"
                        >
                          <template v-if="hasCo2PerKmKg" #tooltip>{{
                            $t('results_total_unit_carbon_footprint_tooltip', {
                              value: $nOrDash(co2PerKmKg, FORMAT_CO2_PER_KM),
                              unit: $t('results_kg_co2eq_per_km'),
                            })
                          }}</template>
                        </BigNumber>
                        <q-separator vertical />
                        <BigNumber
                          :title="$t('results_unit_carbon_footprint')"
                          :number="
                            formatPercentChange(
                              getModuleResult(module)!
                                .year_comparison_percentage,
                            )
                          "
                          :unit="yearComparisonUnit"
                          :color="yearComparisonColor"
                          :comparison="yearComparisonText"
                          :comparison-highlight="`${getModuleConfig(
                            module,
                          ).totalFormatter(
                            getModuleResult(module)!
                              .previous_year_total_tonnes_co2eq,
                          )}${$t('results_units_tonnes')}`"
                          :bordered="false"
                        >
                        </BigNumber>
                        <q-separator vertical />
                        <BigNumber
                          :title="fteBigNumberTitle"
                          :number="
                            getModuleConfig(module)?.totalFormatter(
                              getModuleResult(module)!.tonnes_co2eq_per_fte,
                            )
                          "
                          :comparison="
                            $t('results_paris_agreement_value', {
                              value: `${$nOrDash(2)}${$t('results_units_tonnes')}`,
                            })
                          "
                          :comparison-highlight="`${$nOrDash(2)}${$t('results_units_tonnes')}`"
                          :color-style="getModuleIconColors(module).iconColor"
                          :bordered="false"
                        >
                        </BigNumber>
                      </div>
                    </template>

                    <!-- Module not in results: show validation placeholder -->
                    <template v-else>
                      <q-card flat bordered class="validation-required-card">
                        <q-card-section
                          class="validation-required-card__content"
                        >
                          <q-icon
                            name="o_info"
                            size="md"
                            color="accent"
                            class="q-mb-md"
                          />
                          <div
                            class="text-h6 text-weight-medium text-center q-mb-sm"
                          >
                            {{
                              $t('results_validate_module_title', {
                                module: $t(module),
                              })
                            }}
                          </div>
                          <div class="text-body2 text-secondary text-center">
                            {{ $t('results_validate_module_message') }}
                          </div>
                        </q-card-section>
                      </q-card>
                    </template>
                  </div>
                </template>
              </q-expansion-item>
            </template>
          </template>
        </q-card>
        <q-card v-if="showItFocusSection" flat bordered class="q-pa-none">
          <ItFocusSection
            :data="moduleStore.state.itBreakdown"
            :loading="moduleStore.state.loadingItBreakdown"
            :co2-per-km-kg="co2PerKmKg"
            :year="currentYear"
          />
        </q-card>

        <!-- Additional Data -->
        <q-card v-if="viewAdditionalData" flat bordered>
          <div class="q-pa-xl flex justify-between items-center">
            <div>
              <div class="flex items-center no-wrap q-gutter-sm">
                <h2 class="text-h2 text-weight-medium q-mb-none">
                  {{ $t('results_additional_title') }}
                </h2>
              </div>
              <span class="text-body1 text-secondary">{{
                $t('results_additional_subtitle')
              }}</span>
            </div>
          </div>
          <q-separator />
          <q-card-section class="q-px-none q-pb-none q-pt-none">
            <AdditionalCategoriesSection
              :commuting-row="commutingRow"
              :food-row="foodRow"
              :waste-row="wasteRow"
              :embodied-energy-row="embodiedEnergyRow"
              :embodied-energy-by-category="embodiedEnergyByCategory"
              :headcount-validated="isModuleValidated(MODULES.Headcount)"
              :buildings-validated="isModuleValidated(MODULES.Buildings)"
            />
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<style scoped lang="scss">
.page-grid {
  gap: 2.5rem;
}

.summary-section {
  display: grid;
  gap: 1rem;
}

.results-overview__summary {
  padding: 0;
}

.results-overview__charts {
  padding: 0;
}

.results-summary-row {
  display: flex;
  flex-direction: row;
  align-items: stretch;
}

.results-summary-row__item {
  flex: 1;

  :deep(.q-card) {
    border: none !important;
    box-shadow: none !important;
  }
}

.sections-grid {
  display: grid;
  gap: 2.5rem;
}

.defer-render {
  content-visibility: auto;
  contain-intrinsic-size: 1px 1200px;
}

.module-stats-row {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  border-top: 1px solid rgba(0, 0, 0, 0.12);

  > :not(.q-separator) {
    flex: 1;
  }

  :deep(.q-card) {
    border: none !important;
    box-shadow: none !important;
  }
}

:deep(.q-expansion-item__content > .q-separator:last-child) {
  display: none;
}

.results-charts-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  contain: layout style;
}

.results-charts-grid__main,
.results-charts-grid__side {
  display: flex;
  flex-direction: column;
  min-width: 0;

  :deep(.q-card) {
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
  }
}

.results-charts-grid__separator {
  display: none;
}

@media (min-width: 1024px) {
  .results-charts-grid {
    flex-direction: row;
    align-items: stretch;
    gap: 0;
  }

  .results-charts-grid__main {
    flex: 2;
  }

  .results-charts-grid__side {
    flex: 1;
  }

  .results-charts-grid__separator {
    display: block;
    align-self: stretch;
  }
}

.additional-expand-arrow {
  transition: transform 150ms ease;
}

.additional-expand-arrow--open {
  transform: rotate(180deg);
}

.validation-required-card {
  min-height: 200px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: rgba(0, 0, 0, 0.02);
  border: 1px dashed rgba(0, 0, 0, 0.12);

  &__content {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem;
  }
}

.no-data-styling {
  background-color: rgba(0, 0, 0, 0.02);
  border-radius: 4px;

  :deep(.text-h1) {
    color: rgba(0, 0, 0, 0.38) !important;
  }
}

.objectives-placeholder-frame {
  aspect-ratio: 1380 / 500;
  width: 100%;
}

.objectives-placeholder-image {
  width: 100%;
  height: auto;
  display: block;
}
</style>
