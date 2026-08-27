<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import BigNumber from '@/components/molecules/BigNumber.vue';
import ReportPage from '@/components/organisms/ReportPage.vue';
import ModuleCarbonFootprintChart from '@/components/charts/results/ModuleCarbonFootprintChart.vue';
import { getModuleTypeId } from '@/constant/moduleStates';
import { PLANNER_MODULES } from '@/constant/planner-module-config';
import type { EmissionBreakdownResponse } from '@/stores/modules';
import type { SimulatorPlanYear } from '@/stores/simulatorPlans';
import { formatTonnesCO2 } from '@/utils/number';

interface Props {
  year: SimulatorPlanYear;
  pageNumber: number;
  scope: string;
  planName: string;
  breakdown: EmissionBreakdownResponse | null;
  totalTonnes: number;
}

const props = defineProps<Props>();

const { t } = useI18n();

// The same page prints the Project Grant summary, titled by name rather
// than by its anchor year (#1977).
const pageTitle = computed(() =>
  props.year.is_grant
    ? t('planner_project_grant_title')
    : String(props.year.year),
);

// Inactive modules are excluded from the year's sums and charts, so the report
// names them: a reader seeing a low total needs to know what was left out.
const inactiveModules = computed(() =>
  PLANNER_MODULES.filter((entry) => {
    const module = props.year.modules.find(
      (m) => m.module_type_id === getModuleTypeId(entry.module),
    );
    return module?.is_active === false;
  }).map((entry) => entry.module),
);
</script>

<template>
  <ReportPage :title="pageTitle" :scope="scope" :page-number="pageNumber">
    <h2 class="text-h5 q-mt-none">{{ pageTitle }}</h2>
    <div class="text-body2 text-secondary">
      {{ $t('planner_print_year_subtitle', { name: planName }) }}
    </div>

    <div class="year-facts q-mt-md">
      <div>
        <span class="year-facts__label">
          {{ $t('planner_reference_year_label') }}
        </span>
        <span class="year-facts__value">
          {{ year.reference_year ?? $t('planner_print_no_reference_year') }}
        </span>
      </div>
      <div v-if="inactiveModules.length">
        <span class="year-facts__label">
          {{ $t('planner_print_excluded_modules') }}
        </span>
        <span class="year-facts__value">
          {{ inactiveModules.map((module) => $t(module)).join(', ') }}
        </span>
      </div>
    </div>

    <div class="q-mt-md">
      <BigNumber
        :title="$t('planner_print_year_total')"
        :number="formatTonnesCO2(totalTonnes)"
        color="info"
        :print-mode="true"
      />
    </div>

    <section class="q-mt-md">
      <ModuleCarbonFootprintChart
        :breakdown-data="breakdown"
        :title="$t('planner_print_year_chart_title', { year: pageTitle })"
        :view-additional-data="true"
        :print-mode="true"
        :enforce-module-activation="false"
        :active-categories-only="true"
      />
    </section>
  </ReportPage>
</template>

<style scoped lang="scss">
.year-facts {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;

  &__label {
    opacity: 0.7;
    margin-right: 6px;
  }

  &__value {
    font-weight: 600;
  }
}
</style>
