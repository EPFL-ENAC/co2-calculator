<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ModuleCharts from 'src/components/organisms/module/ModuleCharts.vue';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import type { ModuleResult } from 'src/api/modules';
import type { ModuleConfig } from 'src/constant/moduleConfig';
import type { Module } from 'src/constant/modules';

interface Props {
  module: Module;
  pageNumber: number;
  moduleResult: ModuleResult | undefined;
  moduleConfig: ModuleConfig | undefined;
  totalFte: number | null | undefined;
  hasCo2PerKmKg: boolean;
  co2PerKmKg: number;
  currentYear: number;
}

const props = defineProps<Props>();

const { t, te } = useI18n();

const FORMAT_INTEGER = {
  options: { minimumFractionDigits: 0, maximumFractionDigits: 0 },
};
const FORMAT_CO2_PER_KM = {
  options: { minimumFractionDigits: 2, maximumFractionDigits: 2 },
};

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

function getTotalModuleCarbonFootprintTitle(): string {
  const specificKey = `results_total_module_carbon_footprint_${props.module}`;
  if (te(specificKey)) return t(specificKey);
  return t('results_total_module_carbon_footprint', {
    module: t(props.module),
  });
}
</script>

<template>
  <ReportPage :title="$t(module)" :page-number="pageNumber">
    <h2 class="text-h5 q-mt-none report-h2">
      {{ $t(module) }}
    </h2>
    <div class="text-body2 text-secondary report-subtitle">
      {{ $t('results_subtitle', { year: currentYear }) }}
    </div>

    <div class="q-mt-md">
      <template v-if="moduleResult">
        <div class="grid-3-col grid-compact q-mt-md">
          <BigNumber
            :title="getTotalModuleCarbonFootprintTitle()"
            :number="
              moduleConfig?.totalFormatter(moduleResult.total_tonnes_co2eq)
            "
            :comparison="
              hasCo2PerKmKg
                ? $t('results_equivalent_to_car', {
                    km: $nOrDash(
                      moduleResult.equivalent_car_km,
                      FORMAT_INTEGER,
                    ),
                    value: `${$nOrDash(co2PerKmKg, FORMAT_CO2_PER_KM)}`,
                  })
                : undefined
            "
            :comparison-highlight="`${$nOrDash(moduleResult.equivalent_car_km, FORMAT_INTEGER)}km`"
            color="negative"
            :print-mode="true"
          />

          <BigNumber
            :title="
              $t('results_module_carbon_footprint', { module: $t(module) })
            "
            :number="
              formatPercentChange(moduleResult.year_comparison_percentage)
            "
            :unit="
              $t('results_compared_to', { year: (currentYear - 1).toString() })
            "
            :color="
              moduleResult.year_comparison_percentage == null
                ? undefined
                : moduleResult.year_comparison_percentage < 0
                  ? 'positive'
                  : 'negative'
            "
            :comparison="
              $t('results_compared_to_value_of', {
                value: `${moduleConfig?.totalFormatter(
                  moduleResult.previous_year_total_tonnes_co2eq,
                )}${$t('results_units_tonnes')}`,
              })
            "
            :comparison-highlight="`${moduleConfig?.totalFormatter(
              moduleResult.previous_year_total_tonnes_co2eq,
            )}${$t('results_units_tonnes')}`"
            :print-mode="true"
          />

          <BigNumber
            :title="
              totalFte == null
                ? $t('results_carbon_footprint_per_FTE_no_headcount')
                : $t('results_carbon_footprint_per_fte', {
                    FTE: $nOrDash(totalFte, {
                      options: { maximumFractionDigits: 1 },
                    }),
                  })
            "
            :number="
              moduleConfig?.totalFormatter(moduleResult.tonnes_co2eq_per_fte)
            "
            :comparison="
              $t('results_paris_agreement_value', {
                value: `${$nOrDash(2)}${$t('results_units_tonnes')}`,
              })
            "
            :comparison-highlight="`${$nOrDash(2)}${$t('results_units_tonnes')}`"
            color="negative"
            :print-mode="true"
          >
            <template #tooltip>{{
              $t('results-stats-paris-agreement-title')
            }}</template>
          </BigNumber>
        </div>
      </template>

      <q-card flat bordered class="q-pa-lg q-mt-md print-avoid-break">
        <div class="text-body1 text-weight-medium q-ml-sm q-mb-none">
          {{
            $t('results_module_chart_emission_types', { module: $t(module) })
          }}
        </div>
        <ModuleCharts
          :type="module"
          forced-view="type"
          :show-controls="false"
        />
      </q-card>

      <q-card flat bordered class="q-pa-lg q-mt-md print-avoid-break">
        <div class="text-body1 text-weight-medium q-ml-sm q-mb-none">
          {{ $t('results_module_chart_breakdown', { module: $t(module) }) }}
        </div>
        <ModuleCharts
          :type="module"
          forced-view="breakdown"
          :show-controls="false"
        />
      </q-card>
    </div>
  </ReportPage>
</template>

<style scoped lang="scss">
.grid-3-col {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.grid-compact {
  gap: 10px;
}

.report-h2 {
  letter-spacing: -0.01em;
}

.report-subtitle {
  line-height: 1.35;
}

.print-avoid-break {
  break-inside: avoid;
  page-break-inside: avoid;
}

@media (min-width: 1024px) {
  .grid-3-col {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media print {
  .grid-3-col {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
