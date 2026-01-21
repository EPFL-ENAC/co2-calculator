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
import DistibutionsChart from 'src/components/charts/results/DistibutionsChart.vue';
import { nOrDash } from 'src/utils/number';
import { api } from 'src/api/http';

import Co2Timeline from 'src/components/organisms/layout/Co2Timeline.vue';
import ModuleCharts from 'src/components/organisms/module/ModuleCharts.vue';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useTimelineStore } from 'src/stores/modules';
import { MODULES, Module } from 'src/constant/modules';
import { MODULE_STATES } from 'src/constant/moduleStates';
const { t } = useI18n();

const workspaceStore = useWorkspaceStore();
const timelineStore = useTimelineStore();
const currentYear = computed(() => {
  return workspaceStore.selectedYear ?? new Date().getFullYear();
});

interface UnitTotals {
  total_kg_co2eq: number | null;
  total_tonnes_co2eq: number | null;
  total_fte: number | null;
  kg_co2eq_per_fte: number | null;
  previous_year_total_kg_co2eq: number | null;
  previous_year_total_tonnes_co2eq: number | null;
  year_comparison_percentage: number | null;
}

const unitTotals = ref<UnitTotals | null>(null);
const unitTotalsLoading = ref(false);

async function fetchUnitTotals() {
  const unitId = workspaceStore.selectedUnit?.id;
  if (!unitId) return;

  try {
    unitTotalsLoading.value = true;
    const totals = await api
      .get(`unit/${unitId}/${currentYear.value}/totals`)
      .json<UnitTotals>();
    unitTotals.value = totals;
  } catch (error) {
    console.error('Error fetching unit totals:', error);
    unitTotals.value = null;
  } finally {
    unitTotalsLoading.value = false;
  }
}

onMounted(() => {
  fetchUnitTotals();
});

// Watch for year/unit changes
watch(
  () => [workspaceStore.selectedUnit?.id, currentYear.value],
  () => {
    fetchUnitTotals();
  },
);

const isModuleValidated = (module: string) => {
  return timelineStore.itemStates[module as Module] === MODULE_STATES.Validated;
};

const viewUncertainties = ref(false);
const compareYears = ref(false);

const getModuleConfig = (module: string) => MODULES_CONFIG[module];

// TODO: Replace with actual backend data when available
// This function will get the number value from backend response using numberKey
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const getNumberValue = (_module: string, _numberKey: string): string => {
  return nOrDash(37250);
};

const calculateEquivalentKm = (
  totalCo2Kg: number,
  co2PerKmKg: number,
): number => {
  return totalCo2Kg / co2PerKmKg;
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

      <q-card flat class="grid-3-col">
        <BigNumber
          :title="$t('results_total_unit_carbon_footprint')"
          number="37'250"
          :comparison="
            $t('results_equivalent_to_car', {
              km: nOrDash(calculateEquivalentKm(37250, 0.34)),
              value: `${nOrDash(0.34)}`,
            })
          "
          :comparison-highlight="`${nOrDash(calculateEquivalentKm(37250, 0.34))}km`"
          color="negative"
        >
          <template #tooltip>{{
            $t('results_total_unit_carbon_footprint_tooltip', {
              value: nOrDash(0.34),
              unit: $t('results_kg_co2eq_per_km'),
            })
          }}</template>
        </BigNumber>
        <BigNumber
          :title="$t('results_carbon_footprint_per_fte')"
          number="8.2"
          :comparison="
            $t('results_paris_agreement_value', {
              value: `${nOrDash(2)}${$t('results_units_tonnes')}`,
            })
          "
          :comparison-highlight="`${nOrDash(2)}${$t('results_units_tonnes')}`"
          color="negative"
        >
          <template #tooltip>{{
            $t('results_paris_agreement_tooltip')
          }}</template>
        </BigNumber>
        <BigNumber
          :title="$t('results_unit_carbon_footprint')"
          number="-11.3%"
          :unit="$t('results_compared_to', { year: '2023' })"
          color="positive"
          :comparison="
            $t('results_compared_to_value_of', {
              value: `${nOrDash(48)}${$t('results_units_tonnes')}`,
            })
          "
          :comparison-highlight="`${nOrDash(48)}${$t('results_units_tonnes')}`"
        >
        </BigNumber>
      </q-card>
      <q-card flat class="grid-2-col">
        <ModuleCarbonFootprintChart :view-uncertainties="viewUncertainties" />
        <CarbonFootPrintPerPersonChart />
        
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
          <q-card flat bordered class="q-pa-none q-mt-xl">
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
                <q-card
                  v-if="getModuleConfig(module)?.resultBigNumbers"
                  flat
                  class="grid-3-col q-mb-lg"
                >
                  <BigNumber
                    :title="
                      $t('results_total_module_carbon_footprint', {
                        module: $t(module),
                      })
                    "
                    number="37'250"
                    :comparison="
                      $t('results_equivalent_to_car', {
                        km: nOrDash(calculateEquivalentKm(37250, 0.34)),
                        value: `${nOrDash(0.34)}`,
                      })
                    "
                    :comparison-highlight="`${nOrDash(0.34)} ${$t('results_kg_co2eq_per_km')}`"
                    color="negative"
                  >
                    <template #tooltip>{{
                      $t('results_total_unit_carbon_footprint_tooltip', {
                        value: `${nOrDash(0.34)}${$t('results_t_co2eq_per_km')}`,
                      })
                    }}</template>
                  </BigNumber>
                  <BigNumber
                    :title="$t('results_carbon_footprint_per_fte')"
                    number="8.2"
                    :comparison="
                      $t('results_paris_agreement_value', {
                        value: `${nOrDash(2)}${$t('results_units_tonnes')}`,
                      })
                    "
                    :comparison-highlight="`${nOrDash(2)}${$t('results_units_tonnes')}`"
                    color="negative"
                  >
                    <template #tooltip>{{
                      $t('results_paris_agreement_tooltip')
                    }}</template>
                  </BigNumber>
                  <BigNumber
                    :title="
                      $t('results_module_carbon_footprint', {
                        module: $t(module),
                      })
                    "
                    number="-11.3%"
                    :unit="$t('results_compared_to', { year: '2023' })"
                    color="positive"
                    :comparison="
                      $t('results_compared_to_value_of', {
                        value: `${nOrDash(48)}${$t('results_units_tonnes')}`,
                      })
                    "
                    :comparison-highlight="`${nOrDash(48)}${$t('results_units_tonnes')}`"
                  >
                  </BigNumber>
                </q-card>
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
                  <q-card v-if="unitTotals" flat class="grid-3-col q-mb-lg">
                    <BigNumber
                      :title="$t('results_total_unit_carbon_footprint')"
                      :number="
                        unitTotals.total_tonnes_co2eq
                          ? nOrDash(unitTotals.total_tonnes_co2eq)
                          : '-'
                      "
                      :comparison="
                        $t('results_equivalent_to_car', {
                          km: nOrDash(
                            calculateEquivalentKm(
                              unitTotals.total_kg_co2eq || 0,
                              0.34,
                            ),
                          ),
                          value: `${nOrDash(0.34)}`,
                        })
                      "
                      :comparison-highlight="`${nOrDash(
                        calculateEquivalentKm(
                          unitTotals.total_kg_co2eq || 0,
                          0.34,
                        ),
                      )}km`"
                      color="negative"
                    >
                      <template #tooltip>{{
                        $t('results_total_unit_carbon_footprint_tooltip', {
                          value: nOrDash(0.34),
                          unit: $t('results_kg_co2eq_per_km'),
                        })
                      }}</template>
                    </BigNumber>
                    <BigNumber
                      :title="$t('results_carbon_footprint_per_fte')"
                      :number="
                        unitTotals.kg_co2eq_per_fte
                          ? nOrDash(unitTotals.kg_co2eq_per_fte / 1000, {
                              options: {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              },
                            })
                          : '-'
                      "
                      :comparison="
                        $t('results_paris_agreement_value', {
                          value: `${nOrDash(2)}${$t('results_units_tonnes')}`,
                        })
                      "
                      :comparison-highlight="`${nOrDash(2)}${$t('results_units_tonnes')}`"
                      color="negative"
                    >
                      <template #tooltip>{{
                        $t('results_paris_agreement_tooltip')
                      }}</template>
                    </BigNumber>
                    <div
                      :class="{
                        'no-data-styling':
                          unitTotals.year_comparison_percentage === null,
                      }"
                    >
                      <BigNumber
                        :title="$t('results_unit_carbon_footprint')"
                        :number="
                          unitTotals.year_comparison_percentage !== null
                            ? `${unitTotals.year_comparison_percentage > 0 ? '+' : ''}${nOrDash(unitTotals.year_comparison_percentage)}%`
                            : '-'
                        "
                        :unit="
                          $t('results_compared_to', {
                            year: (currentYear - 1).toString(),
                          })
                        "
                        :color="
                          unitTotals.year_comparison_percentage === null
                            ? undefined
                            : unitTotals.year_comparison_percentage < 0
                              ? 'positive'
                              : 'negative'
                        "
                        :comparison="
                          unitTotals.previous_year_total_tonnes_co2eq !== null
                            ? $t('results_compared_to_value_of', {
                                value: `${nOrDash(
                                  unitTotals.previous_year_total_tonnes_co2eq,
                                )}${$t('results_units_tonnes')}`,
                              })
                            : ''
                        "
                        :comparison-highlight="
                          unitTotals.previous_year_total_tonnes_co2eq !== null
                            ? `${nOrDash(
                                unitTotals.previous_year_total_tonnes_co2eq,
                              )}${$t('results_units_tonnes')}`
                            : ''
                        "
                      >
                      </BigNumber>
                    </div>
                  </q-card>
                </template>
                <template
                  v-else-if="
                    module === MODULES.ProfessionalTravel &&
                    !isModuleValidated(module)
                  "
                >
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

                <q-card v-else flat bordered>
                  <q-card-section class="flex items-center q-mb-xs">
                    <q-icon name="o_info" size="xs" color="primary">
                      <q-tooltip
                        v-if="$slots.tooltip"
                        anchor="center right"
                        self="top right"
                        class="u-tooltip"
                      >
                        <slot name="tooltip"></slot>
                      </q-tooltip>
                    </q-icon>
                    <span
                      class="text-body1 text-weight-medium q-ml-sm q-mb-none"
                    >
                      {{ $t('results_equipment_distribution_title') }}
                    </span>
                  </q-card-section>
                  <q-card-section class="chart-container">
                    <DistibutionsChart />
                  </q-card-section>
                </q-card>
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
