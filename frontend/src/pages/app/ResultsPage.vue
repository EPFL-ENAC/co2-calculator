<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { MODULES_LIST } from 'src/constant/modules';
import { MODULES_CONFIG } from 'src/constant/module-config';
import { colorblindMode } from 'src/constant/charts';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ChartContainer from 'src/components/molecules/ChartContainer.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import CarbonFootPrintPerPersonChart from 'src/components/charts/results/CarbonFootPrintPerPersonChart.vue';
import DistibutionsChart from 'src/components/charts/results/DistibutionsChart.vue';
import { formatNumber } from 'src/utils/number';

const { t } = useI18n();

// Use global colorblindMode directly as single source of truth
// No local ref, no watcher, no initialization override
const viewUncertainties = ref(false);

const getModuleConfig = (module: string) => MODULES_CONFIG[module];

// TODO: Replace with actual backend data when available
// This function will get the number value from backend response using numberKey
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const getNumberValue = (_module: string, _numberKey: string): string => {
  return formatNumber(37250);
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
  <q-page class="page-grid">
    <q-card flat bordered class="q-pa-xl">
      <div class="flex justify-between items-center">
        <div>
          <h2 class="text-h2 text-weight-medium">
            {{ $t('results_title') }}
          </h2>
          <span class="text-body1 text-secondary">{{
            $t('results_subtitle')
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
          </div>
        </div>
      </div>
    </q-card>
    <q-card flat class="grid-3-col">
      <BigNumber
        :title="$t('results_total_unit_carbon_footprint')"
        number="37'250"
        :comparison="$t('results_equivalent_to_car', { km: '10\'000' })"
        comparison-highlight="10'000"
        color="negative"
      >
        <template #tooltip>tip</template>
      </BigNumber>
      <BigNumber
        :title="$t('results_carbon_footprint_per_fte')"
        number="8.2"
        :comparison="$t('results_paris_agreement_budget')"
        comparison-highlight="2t CO₂-eq"
        color="negative"
      >
        <template #tooltip>tooltip</template>
      </BigNumber>
      <BigNumber
        :title="$t('results_unit_carbon_footprint')"
        number="-11.3%"
        :unit="$t('results_compared_to', { year: '2022' })"
        color="positive"
        :comparison="$t('results_value_of', { value: '42\'500' })"
        comparison-highlight="42'500 t CO₂-eq"
      >
        <template #tooltip>tooltip</template>
      </BigNumber>
    </q-card>
    <q-card flat class="grid-2-col">
      <ModuleCarbonFootprintChart />

      <ChartContainer :title="$t('results_carbon_footprint_per_person')">
        <template #tooltip>tooltip</template>
        <CarbonFootPrintPerPersonChart />
      </ChartContainer>
    </q-card>
    <div class="q-mt-xl">
      <q-card bordered flat class="q-pa-xl">
        <div class="flex justify-between items-center">
          <div>
            <h2 class="text-h2 text-weight-medium">
              {{ $t('results_by_category_title') }}
            </h2>
            <span class="text-body1 text-secondary">{{
              $t('results_by_category_subtitle', { year: '2024' })
            }}</span>
          </div>
        </div>
      </q-card>
      <template v-for="module in MODULES_LIST" :key="module">
        <q-card flat bordered class="q-pa-none q-mt-xl">
          <q-expansion-item expand-separator default-opened>
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
                  v-if="getModuleConfig(module)?.uncertainty"
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

            <div class="q-pa-lg">
              <q-card
                v-if="getModuleConfig(module)?.resultBigNumbers"
                flat
                class="grid-3-col q-mb-lg"
              >
                <BigNumber
                  v-for="(bigNumber, id) in getModuleConfig(module)
                    ?.resultBigNumbers"
                  :key="id"
                  :title="$t(bigNumber.titleKey)"
                  :number="getNumberValue(module, bigNumber.numberKey)"
                  :unit="
                    bigNumber.unitKey
                      ? $t(bigNumber.unitKey, bigNumber.unitParams || {})
                      : undefined
                  "
                  :comparison="
                    bigNumber.comparisonKey
                      ? $t(
                          bigNumber.comparisonKey,
                          bigNumber.comparisonParams || {},
                        )
                      : undefined
                  "
                  :comparison-highlight="bigNumber.comparisonHighlight"
                  :color="bigNumber.color"
                >
                  <template #tooltip>
                    {{
                      bigNumber.tooltipKey
                        ? $t(bigNumber.tooltipKey)
                        : 'tooltip'
                    }}
                  </template>
                </BigNumber>
              </q-card>
              <q-card flat bordered>
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
                  <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
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
  </q-page>
</template>
