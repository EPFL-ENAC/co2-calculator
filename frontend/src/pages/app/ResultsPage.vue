<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { MODULES_LIST } from 'src/constant/modules';
import { MODULES_CONFIG } from 'src/constant/module-config';
import { colorblindMode } from 'src/constant/charts';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import CarbonFootPrintPerPersonChart from 'src/components/charts/results/CarbonFootPrintPerPersonChart.vue';
import {
  getResultsSummary,
  type ResultsSummary,
  type ModuleResult,
} from 'src/api/modules';

import Co2Timeline from 'src/components/organisms/layout/Co2Timeline.vue';
import ModuleCharts from 'src/components/organisms/module/ModuleCharts.vue';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useTimelineStore, useModuleStore } from 'src/stores/modules';
import { MODULES, Module } from 'src/constant/modules';
import { MODULE_STATES, getModuleTypeId } from 'src/constant/moduleStates';
const { t } = useI18n();

const FORMAT_1_DECIMAL = {
  options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
};
const FORMAT_INTEGER = {
  options: { minimumFractionDigits: 0, maximumFractionDigits: 0 },
};

const co2PerKmKg = computed(() => resultsSummary.value?.co2_per_km_kg ?? 0);

const percentChangeFormatter = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: 'always',
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

async function fetchResultsSummary() {
  const carbonReportId = workspaceStore.selectedCarbonReport?.id;
  if (!carbonReportId) return;

  try {
    resultsSummaryLoading.value = true;
    resultsSummary.value = await getResultsSummary(carbonReportId);
  } catch (error) {
    console.error('Error fetching results summary:', error);
    resultsSummary.value = null;
  } finally {
    resultsSummaryLoading.value = false;
  }
}

async function fetchEmissionBreakdown() {
  const carbonReportId = workspaceStore.selectedCarbonReport?.id;
  if (!carbonReportId) return;
  await moduleStore.getEmissionBreakdown(carbonReportId);
}

onMounted(() => {
  fetchResultsSummary();
  fetchEmissionBreakdown();
});

// Watch for year/unit changes
watch(
  () => [workspaceStore.selectedCarbonReport?.id, currentYear.value],
  () => {
    fetchResultsSummary();
    fetchEmissionBreakdown();
  },
);

const isModuleValidated = (module: string) => {
  return timelineStore.itemStates[module as Module] === MODULE_STATES.Validated;
};

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

const viewUncertainties = ref(false);
const compareYears = ref(false);

const getModuleConfig = (module: string) => MODULES_CONFIG[module];
const getModuleFormatOptions = (module: string) => ({
  options: getModuleConfig(module)?.numberFormatOptions,
});

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

const downloadPDF = () => {
  // Open browser print dialog where user can save as PDF
  window.print();
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
            $nOrDash(
              resultsSummary.unit_totals.total_tonnes_co2eq,
              FORMAT_INTEGER,
            )
          "
          :comparison="
            $t('results_equivalent_to_car', {
              km: $n(resultsSummary.unit_totals.equivalent_car_km),
              value: `${$nOrDash(co2PerKmKg)}`,
            })
          "
          :comparison-highlight="`${$n(resultsSummary.unit_totals.equivalent_car_km)}km`"
          color="negative"
        >
          <template #tooltip>{{
            $t('results_total_unit_carbon_footprint_tooltip', {
              value: $nOrDash(co2PerKmKg),
              unit: $t('results_kg_co2eq_per_km'),
            })
          }}</template>
        </BigNumber>
        <BigNumber
          :title="$t('results_carbon_footprint_per_fte')"
          :number="
            $nOrDash(
              resultsSummary.unit_totals.tonnes_co2eq_per_fte,
              FORMAT_INTEGER,
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
              $t('results_compared_to', {
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
              $t('results_compared_to_value_of', {
                value: `${$nOrDash(
                  resultsSummary.unit_totals.previous_year_total_tonnes_co2eq,
                  FORMAT_1_DECIMAL,
                )}${$t('results_units_tonnes')}`,
              })
            "
            :comparison-highlight="`${$nOrDash(
              resultsSummary.unit_totals.previous_year_total_tonnes_co2eq,
            )}${$t('results_units_tonnes')}`"
          >
          </BigNumber>
        </div>
      </q-card>
      <q-card flat class="grid-2-col">
        <ModuleCarbonFootprintChart
          :view-uncertainties="viewUncertainties"
          :breakdown-data="moduleStore.state.emissionBreakdown"
        />
        <CarbonFootPrintPerPersonChart
          :view-uncertainties="viewUncertainties"
          :per-person-breakdown="
            moduleStore.state.emissionBreakdown?.per_person_breakdown
          "
          :validated-categories="
            moduleStore.state.emissionBreakdown?.validated_categories
          "
          :headcount-validated="
            moduleStore.state.emissionBreakdown?.validated_categories?.includes(
              'Commuting',
            ) ?? false
          "
        />
      </q-card>

      <div class="q-mt-xl">
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
        <template v-for="module in MODULES_LIST" :key="module">
          <q-card
            v-if="module !== MODULES.Headcount"
            flat
            bordered
            class="q-pa-none q-mt-xl"
          >
            <q-expansion-item expand-separator>
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
              <q-separator />

              <div class="q-px-lg">
                <!-- Module has results in the summary -->
                <template v-if="getModuleResult(module)">
                  <!-- Professional travel specific charts -->
                  <template
                    v-if="
                      module === MODULES.ProfessionalTravel &&
                      isModuleValidated(module)
                    "
                  >
                    <ModuleCharts
                      :type="MODULES.ProfessionalTravel"
                      :show-evolution-chart="true"
                    />
                  </template>
                  <q-card flat class="grid-3-col q-mb-lg">
                    <BigNumber
                      :title="
                        $t('results_total_module_carbon_footprint', {
                          module: $t(module),
                        })
                      "
                      :number="
                        $nOrDash(
                          getModuleResult(module)!.total_tonnes_co2eq,
                          getModuleFormatOptions(module),
                        )
                      "
                      :comparison="
                        $t('results_equivalent_to_car', {
                          km: $nOrDash(
                            getModuleResult(module)!.equivalent_car_km,
                            FORMAT_INTEGER,
                          ),
                          value: `${$nOrDash(co2PerKmKg)}`,
                        })
                      "
                      :comparison-highlight="`${$nOrDash(
                        getModuleResult(module)!.equivalent_car_km,
                        FORMAT_INTEGER,
                      )}km`"
                      color="negative"
                    >
                      <template #tooltip>{{
                        $t('results_total_unit_carbon_footprint_tooltip', {
                          value: $nOrDash(co2PerKmKg),
                          unit: $t('results_kg_co2eq_per_km'),
                        })
                      }}</template>
                    </BigNumber>
                    <BigNumber
                      :title="$t('results_carbon_footprint_per_fte')"
                      :number="
                        $nOrDash(
                          getModuleResult(module)!.tonnes_co2eq_per_fte,
                          getModuleFormatOptions(module),
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
                    <div
                      :class="{
                        'no-data-styling':
                          getModuleResult(module)!.year_comparison_percentage ==
                          null,
                      }"
                    >
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
                            value: `${$nOrDash(
                              getModuleResult(module)!
                                .previous_year_total_tonnes_co2eq,
                            )}${$t('results_units_tonnes')}`,
                          })
                        "
                        :comparison-highlight="`${$nOrDash(
                          getModuleResult(module)!
                            .previous_year_total_tonnes_co2eq,
                        )}${$t('results_units_tonnes')}`"
                      >
                      </BigNumber>
                    </div>
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
            </q-expansion-item>
          </q-card>
        </template>
      </div>
      <div class="q-mt-xl">
        <q-card flat bordered class="q-pa-xl">
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
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<style scoped lang="scss">
.validation-required-card {
  min-height: 200px;
  background-color: rgba(0, 0, 0, 0.02);
  border: 1px dashed rgba(0, 0, 0, 0.12);
  margin: 1rem 0;

  &__content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    min-height: 200px;
  }
}

.no-data-styling {
  background-color: rgba(0, 0, 0, 0.02);
  border-radius: 4px;

  :deep(.text-h1) {
    color: rgba(0, 0, 0, 0.38) !important;
  }
}
</style>
