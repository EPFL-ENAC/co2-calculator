<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  h,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue';
import { QSkeleton } from 'quasar';
import { MODULES_LIST, MODULES, type Module } from 'src/constant/modules';
import { MODULES_CONFIG } from 'src/constant/module-config';

import { colorblindMode } from 'src/constant/charts';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import {
  getResultsSummary,
  type ResultsSummary,
  type ModuleResult,
} from 'src/api/modules';

import { useWorkspaceStore } from 'src/stores/workspace';
import { useTimelineStore, useModuleStore } from 'src/stores/modules';
import { IT_FOCUS_SOURCE_MODULES } from 'src/constant/itFocus';
import { MODULE_STATES, getModuleTypeId } from 'src/constant/moduleStates';
import { useI18n } from 'vue-i18n';

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

const TimelineSkeleton = () =>
  h(QSkeleton, {
    type: 'rect',
    height: '88px',
    class: 'full-width q-mb-sm',
  });

const Co2Timeline = defineAsyncComponent({
  loader: () => import('src/components/organisms/layout/Co2Timeline.vue'),
  loadingComponent: TimelineSkeleton,
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
const currentYear = computed(() => {
  return workspaceStore.selectedYear ?? new Date().getFullYear();
});

const resultsSummary = ref<ResultsSummary | null>(null);
const resultsSummaryLoading = ref(false);

const hideResearchFacilities = ref(false);

const mountPrimaryCharts = ref(false);

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

onMounted(() => {
  void fetchResultsSummary();
  // Defer heavy breakdown fetches: charts mount on idle, avoid blocking initial paint.
  const scheduleIdle =
    window.requestIdleCallback ??
    ((cb: () => void) => window.setTimeout(cb, 200));
  scheduleIdle(() => {
    void fetchEmissionBreakdown();
  });
  scheduleIdle(() => {
    void fetchItBreakdown();
  });

  // Defer ECharts mounting to reduce main-thread blocking during initial paint.
  scheduleIdle(() => {
    mountPrimaryCharts.value = true;
  });
});

// Watch for year/unit changes
watch(
  () => [
    workspaceStore.selectedCarbonReport?.id,
    currentYear.value,
    hideResearchFacilities.value,
  ],
  () => {
    moduleStore.invalidateEmissionBreakdown();
    void fetchResultsSummary();
    const scheduleIdle =
      window.requestIdleCallback ??
      ((cb: () => void) => window.setTimeout(cb, 200));
    scheduleIdle(() => {
      void fetchEmissionBreakdown();
    });
    scheduleIdle(() => {
      void fetchItBreakdown();
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

const viewUncertainties = ref(false);
const hideAdditionalData = ref(false);
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

const getModuleConfig = (module: string) => MODULES_CONFIG[module];

const downloadPDF = () => {
  // Open browser print dialog where user can save as PDF
  window.print();
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
    <Co2Timeline />
    <q-separator />
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
              color="accent"
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
                v-model="colorblindMode"
                :label="$t('results_colorblind_mode')"
                color="accent"
                class="text-weight-medium"
                size="xs"
              />
              <q-checkbox
                v-model="viewUncertainties"
                :label="$t('results_view_uncertainties')"
                color="accent"
                class="text-weight-medium"
                size="xs"
              />
              <q-checkbox
                v-model="hideResearchFacilities"
                :label="$t('results_hide_research_facilities')"
                color="accent"
                class="text-weight-medium"
                size="xs"
              />
              <q-checkbox
                v-model="hideAdditionalData"
                :label="$t('results_hide_additional_data')"
                color="accent"
                class="text-weight-medium"
                size="xs"
              />
              <q-separator class="q-my-sm" />
              <q-checkbox
                v-model="compareYears"
                :label="$t('results_compare_years')"
                color="accent"
                class="text-weight-medium"
                size="xs"
              />
            </div>
          </div>
        </div>
      </q-card>
      <q-card v-if="resultsSummary" flat class="grid-3-col">
        <BigNumber
          :title="$t('results_total_unit_carbon_footprint')"
          :number="
            $nOrDash(adjustedTotalTonnes, {
              options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
            })
          "
          tooltip-placement="comparison"
          :comparison="
            hasCo2PerKmKg
              ? $t('results_equivalent_to_car', {
                  km: $n(resultsSummary.unit_totals.equivalent_car_km),
                  value: `${$nOrDash(co2PerKmKg, FORMAT_CO2_PER_KM)}`,
                })
              : undefined
          "
          :comparison-highlight="`${$n(resultsSummary.unit_totals.equivalent_car_km)}km`"
          color="negative"
        >
          <template v-if="hasCo2PerKmKg" #tooltip>{{
            $t('results_total_unit_carbon_footprint_tooltip', {
              value: $nOrDash(co2PerKmKg, FORMAT_CO2_PER_KM),
              unit: $t('results_kg_co2eq_per_km'),
            })
          }}</template>
        </BigNumber>

        <div
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
            :unit="
              resultsSummary.unit_totals.year_comparison_percentage == null
                ? $t('results_no_comparison_year_available')
                : $t('results_compared_to', {
                    year: (currentYear - 1).toString(),
                  })
            "
            :color="
              resultsSummary.unit_totals.year_comparison_percentage == null
                ? undefined
                : resultsSummary.unit_totals.year_comparison_percentage < 0
                  ? 'positive'
                  : 'negative'
            "
            :comparison="
              resultsSummary.unit_totals.year_comparison_percentage == null
                ? undefined
                : $t('results_compared_to_value_of', {
                    value: `${$nOrDash(
                      resultsSummary.unit_totals
                        .previous_year_total_tonnes_co2eq,
                      {
                        options: {
                          minimumFractionDigits: 1,
                          maximumFractionDigits: 1,
                        },
                      },
                    )}${$t('results_units_tonnes')}`,
                  })
            "
            :comparison-highlight="
              resultsSummary.unit_totals.year_comparison_percentage == null
                ? undefined
                : `${$nOrDash(
                    resultsSummary.unit_totals.previous_year_total_tonnes_co2eq,
                    {
                      options: {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1,
                      },
                    },
                  )}${$t('results_units_tonnes')}`
            "
          >
          </BigNumber>
        </div>

        <BigNumber
          :title="
            resultsSummary.unit_totals.total_fte == null
              ? $t('results_carbon_footprint_per_FTE_no_headcount')
              : $t('results_carbon_footprint_per_fte', {
                  FTE: resultsSummary.unit_totals.total_fte,
                })
          "
          :number="
            $nOrDash(adjustedTonnesPerFte, {
              options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
            })
          "
          :comparison="
            $t('results_paris_agreement_value', {
              value: `${$nOrDash(2)}${$t('results_units_tonnes')}`,
            })
          "
          :comparison-highlight="`${$nOrDash(2)}${$t('results_units_tonnes')}`"
          color="negative"
        >
        </BigNumber>
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
      <q-card flat class="results-charts-grid">
        <div class="results-charts-grid__main">
          <template v-if="mountPrimaryCharts">
            <ModuleCarbonFootprintChart
              :breakdown-data="moduleStore.state.emissionBreakdown"
              :view-additional-data="viewAdditionalData"
            />
          </template>
          <q-skeleton v-else type="rect" height="360px" class="full-width" />
        </div>

        <div class="results-charts-grid__side">
          <template v-if="!isModuleValidated(MODULES.Headcount)">
            <q-card flat bordered class="validation-required-card">
              <q-card-section class="validation-required-card__content">
                <q-icon
                  name="o_info"
                  size="md"
                  color="accent"
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
            <q-skeleton v-else type="rect" height="360px" class="full-width" />
          </template>
        </div>
      </q-card>

      <q-card flat bordered class="q-pa-lg">
        <div class="flex justify-between items-center">
          <div>
            <h2 class="text-h2 text-weight-medium">
              {{ $t('results_objectives_2040_title') }}
            </h2>
            <span class="text-body1 text-secondary">{{
              $t('results_objectives_2040_subtitle')
            }}</span>
          </div>
        </div>
        <q-card-section class="q-px-none q-pt-lg q-pb-none">
          <div class="objectives-placeholder-frame">
            <img
              src="/placeholder.svg"
              alt=""
              width="1380"
              height="500"
              decoding="async"
              fetchpriority="low"
              class="objectives-placeholder-image"
            />
          </div>
        </q-card-section>
      </q-card>

      <div>
        <q-card bordered flat class="q-pa-xl">
          <div class="flex justify-between items-center">
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
          </div>
        </q-card>
        <!-- Module Collapse Items -->
        <template v-for="module in MODULES_LIST" :key="module">
          <q-card
            v-if="
              module !== MODULES.Headcount &&
              !(hideResearchFacilities && module === MODULES.ResearchFacilities)
            "
            flat
            bordered
            class="q-pa-none q-mt-xl"
          >
            <q-expansion-item
              v-model="resultsCategoryExpanded[module]"
              expand-separator
            >
              <template #header>
                <div class="flex justify-between items-center">
                  <module-icon
                    :name="module"
                    size="md"
                    color="accent"
                    class="q-mr-sm"
                  />
                  <div class="text-h5 text-weight-medium">{{ $t(module) }}</div>
                  <q-badge
                    v-if="
                      viewUncertainties && getModuleConfig(module)?.uncertainty
                    "
                    outline
                    rounded
                    :color="
                      getUncertainty(getModuleConfig(module)?.uncertainty).color
                    "
                    :label="
                      getUncertainty(getModuleConfig(module)?.uncertainty).label
                    "
                    class="q-ml-sm"
                  />
                </div>
              </template>
              <template v-if="resultsCategoryExpanded[module]">
                <q-separator />

                <div class="q-px-lg">
                  <!-- Module has results in the summary -->
                  <template v-if="getModuleResult(module)">
                    <!-- Per-module treemap -->
                    <template v-if="isModuleValidated(module)">
                      <ModuleCharts
                        :type="module"
                        :show-evolution-chart="
                          module === MODULES.ProfessionalTravel
                        "
                      />
                    </template>
                    <q-card flat class="grid-3-col q-mb-lg">
                      <BigNumber
                        :title="
                          getTotalModuleCarbonFootprintTitle(module as Module)
                        "
                        :number="
                          getModuleConfig(module).totalFormatter(
                            getModuleResult(module)!.total_tonnes_co2eq,
                          )
                        "
                        :comparison="
                          hasCo2PerKmKg
                            ? $t('results_equivalent_to_car', {
                                km: $nOrDash(
                                  getModuleResult(module)!.equivalent_car_km,
                                  FORMAT_INTEGER,
                                ),
                                value: `${$nOrDash(co2PerKmKg, FORMAT_CO2_PER_KM)}`,
                              })
                            : undefined
                        "
                        :comparison-highlight="`${$nOrDash(
                          getModuleResult(module)!.equivalent_car_km,
                          FORMAT_INTEGER,
                        )}km`"
                        color="negative"
                      >
                        <template v-if="hasCo2PerKmKg" #tooltip>{{
                          $t('results_total_unit_carbon_footprint_tooltip', {
                            value: $nOrDash(co2PerKmKg, FORMAT_CO2_PER_KM),
                            unit: $t('results_kg_co2eq_per_km'),
                          })
                        }}</template>
                      </BigNumber>
                      <BigNumber
                        :title="
                          $t('results_module_carbon_footprint', {
                            module: $t(module),
                          })
                        "
                        :number="
                          formatPercentChange(
                            getModuleResult(module)!.year_comparison_percentage,
                          )
                        "
                        :unit="
                          $t('results_compared_to', {
                            year: (currentYear - 1).toString(),
                          })
                        "
                        :color="
                          getModuleResult(module)!.year_comparison_percentage ==
                          null
                            ? undefined
                            : getModuleResult(module)!
                                  .year_comparison_percentage! < 0
                              ? 'positive'
                              : 'negative'
                        "
                        :comparison="
                          $t('results_compared_to_value_of', {
                            value: `${getModuleConfig(module).totalFormatter(
                              getModuleResult(module)!
                                .previous_year_total_tonnes_co2eq,
                            )}${$t('results_units_tonnes')}`,
                          })
                        "
                        :comparison-highlight="`${getModuleConfig(
                          module,
                        ).totalFormatter(
                          getModuleResult(module)!
                            .previous_year_total_tonnes_co2eq,
                        )}${$t('results_units_tonnes')}`"
                      >
                      </BigNumber>
                      <BigNumber
                        :title="
                          resultsSummary.unit_totals.total_fte == null
                            ? $t(
                                'results_carbon_footprint_per_FTE_no_headcount',
                              )
                            : $t('results_carbon_footprint_per_fte', {
                                FTE: resultsSummary.unit_totals.total_fte,
                              })
                        "
                        :number="
                          getModuleConfig(module).totalFormatter(
                            getModuleResult(module)!.tonnes_co2eq_per_fte,
                          )
                        "
                        :comparison="
                          $t('results_paris_agreement_value', {
                            value: `${$nOrDash(2)}${$t('results_units_tonnes')}`,
                          })
                        "
                        :comparison-highlight="`${$nOrDash(2)}${$t('results_units_tonnes')}`"
                        color="negative"
                      >
                        <template #tooltip>{{
                          $t('results_paris_agreement_tooltip')
                        }}</template>
                      </BigNumber>
                    </q-card>
                  </template>

                  <!-- Module not in results: show validation placeholder -->
                  <template v-else>
                    <q-card flat bordered class="validation-required-card">
                      <q-card-section class="validation-required-card__content">
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
          </q-card>
        </template>
        <q-card
          v-if="showItFocusSection"
          flat
          bordered
          class="q-pa-none q-mt-xl"
        >
          <ItFocusSection
            :data="moduleStore.state.itBreakdown"
            :loading="moduleStore.state.loadingItBreakdown"
            :co2-per-km-kg="co2PerKmKg"
            :year="currentYear"
          />
        </q-card>

        <!-- Additional Data -->
        <q-card v-if="viewAdditionalData" flat bordered class="q-mt-xl">
          <div class="q-pa-xl flex justify-between items-center">
            <div>
              <div class="flex items-center no-wrap q-gutter-sm">
                <h2 class="text-h2 text-weight-medium q-mb-none">
                  {{ $t('results_additional_title') }}
                </h2>
                <q-icon name="o_info" size="sm" class="text-primary">
                  <q-tooltip class="text-body2 text-black" max-width="320px">
                    {{ $t('results_additional_waste_tooltip') }}
                  </q-tooltip>
                </q-icon>
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
.results-charts-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

@media (min-width: 1024px) {
  .results-charts-grid {
    grid-template-columns: repeat(3, 1fr);
    align-items: stretch;
  }

  .results-charts-grid__main {
    grid-column: span 2;
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
