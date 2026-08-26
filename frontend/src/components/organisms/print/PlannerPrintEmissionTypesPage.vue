<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import ReportPage from '@/components/organisms/ReportPage.vue';
import PlannerPrintEmissionTypesTable from '@/components/organisms/print/PlannerPrintEmissionTypesTable.vue';
import type { EmissionBreakdownResponse } from '@/stores/modules';
import type { SimulatorPlanYear } from '@/stores/simulatorPlans';

interface Props {
  year: SimulatorPlanYear;
  pageNumber: number;
  scope: string;
  breakdown: EmissionBreakdownResponse | null;
}

const props = defineProps<Props>();

const { t } = useI18n();

const reportTitle = computed(() =>
  props.year.is_grant
    ? t('planner_project_grant_title')
    : String(props.year.year),
);

const categoryRows = computed(() => props.breakdown?.module_breakdown ?? []);
</script>

<template>
  <ReportPage
    :title="$t('planner_print_emission_types_title')"
    :scope="scope"
    :page-number="pageNumber"
    flow
  >
    <h2 class="text-h5 q-mt-none">
      {{ $t('planner_print_emission_types_title') }}
    </h2>
    <div class="text-body2 text-secondary q-mb-lg">
      {{ $t('planner_print_emission_types_subtitle', { report: reportTitle }) }}
    </div>

    <PlannerPrintEmissionTypesTable :category-rows="categoryRows" />
  </ReportPage>
</template>
