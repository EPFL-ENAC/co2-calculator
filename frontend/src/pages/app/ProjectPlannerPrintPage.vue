<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import PlannerPrintHeadcountTable from 'src/components/organisms/print/PlannerPrintHeadcountTable.vue';
import PlannerPrintModulePage from 'src/components/organisms/print/PlannerPrintModulePage.vue';
import PlannerPrintYearPage from 'src/components/organisms/print/PlannerPrintYearPage.vue';
import PrintReportShell from 'src/components/organisms/print/PrintReportShell.vue';
import { useProjectPlannerPrintData } from 'src/composables/print/useProjectPlannerPrintData';
import { formatTonnesCO2 } from 'src/utils/number';
import { toPrintDocumentTitle } from 'src/utils/unitPerimeterLabel';

const { t } = useI18n();

const {
  loading,
  notFound,
  plan,
  planYears,
  yearRangeLabel,
  scopeLabel,
  planBreakdown,
  totalTonnesCo2eq,
  yearBreakdowns,
  yearTotalTonnes,
  headcountRows,
  incompleteModules,
  sheets,
  moduleTables,
  initWorkspaceFromRoute,
  fetchAllData,
} = useProjectPlannerPrintData();

const createdAtLabel = computed(() => {
  const createdAt = plan.value?.created_at;
  if (!createdAt) return '';
  const parsed = new Date(createdAt);
  return Number.isNaN(parsed.getTime())
    ? ''
    : parsed.toLocaleDateString('de-CH');
});

onMounted(async () => {
  const resolved = await initWorkspaceFromRoute();
  if (!resolved) {
    notFound.value = true;
    loading.value = false;
    return;
  }

  await fetchAllData();

  // Chrome seeds the "Save as PDF" filename from the document title.
  document.title = toPrintDocumentTitle(
    plan.value?.name ?? scopeLabel.value,
    t('planner_print_title'),
  );
});
</script>

<template>
  <PrintReportShell
    :loading="loading"
    :empty="notFound || plan === null"
    :empty-message="$t('project_planner_not_found')"
  >
    <template v-if="plan">
      <ReportPage
        :title="$t('planner_print_title')"
        :scope="scopeLabel"
        :page-number="1"
        :is-first="true"
      >
        <h2 class="text-h5 q-mt-none report-h2">
          {{ $t('planner_print_title') }}
        </h2>
        <div class="text-body2 text-secondary">{{ plan.name }}</div>

        <dl class="project-facts q-mt-md">
          <div class="project-facts__row">
            <dt>{{ $t('planner_year_selection_label') }}</dt>
            <dd>{{ yearRangeLabel || '–' }}</dd>
          </div>
          <div v-if="plan.creator_name" class="project-facts__row">
            <dt>{{ $t('planner_print_created_by') }}</dt>
            <dd>{{ plan.creator_name }}</dd>
          </div>
          <div v-if="createdAtLabel" class="project-facts__row">
            <dt>{{ $t('planner_print_created_on') }}</dt>
            <dd>{{ createdAtLabel }}</dd>
          </div>
        </dl>

        <div class="q-mt-md">
          <BigNumber
            :title="$t('planner_results_total_tonnes_co2eq')"
            :number="formatTonnesCO2(totalTonnesCo2eq)"
            :comparison="
              $t('planner_print_total_over_years', {
                count: planYears.length,
              })
            "
            color="info"
            :print-mode="true"
          />
        </div>

        <section class="q-mt-md">
          <ModuleCarbonFootprintChart
            :breakdown-data="planBreakdown"
            :title="$t('planner_results_chart_title', { name: plan.name })"
            :print-mode="true"
          />
        </section>

        <p class="text-caption text-secondary q-mt-md q-mb-none">
          {{ $t('planner_print_methodology_note') }}
        </p>
        <p
          v-if="incompleteModules.length"
          class="text-caption q-mt-sm q-mb-none"
        >
          {{
            $t('planner_print_incomplete_note', {
              modules: incompleteModules.join(', '),
            })
          }}
        </p>
      </ReportPage>

      <template v-for="sheet in sheets" :key="sheet.key">
        <PlannerPrintYearPage
          v-if="sheet.kind === 'year'"
          :year="sheet.year"
          :page-number="sheet.pageNumber"
          :scope="scopeLabel"
          :plan-name="plan.name"
          :breakdown="yearBreakdowns[sheet.year.id] ?? null"
          :total-tonnes="yearTotalTonnes(sheet.year)"
        />

        <ReportPage
          v-else-if="sheet.kind === 'headcount'"
          :title="$t('headcount')"
          :scope="scopeLabel"
          :page-number="sheet.pageNumber"
          flow
        >
          <h2 class="text-h5 q-mt-none">{{ $t('headcount') }}</h2>
          <div class="text-body2 text-secondary q-mb-lg">
            {{ $t('planner_print_module_subtitle', { year: sheet.year.year }) }}
          </div>
          <PlannerPrintHeadcountTable
            :rows="headcountRows[sheet.year.id] ?? []"
          />
        </ReportPage>

        <PlannerPrintModulePage
          v-else
          :module="sheet.module"
          :year="sheet.year.year"
          :page-number="sheet.pageNumber"
          :scope="scopeLabel"
          :tables="moduleTables(sheet.year, sheet.module)"
        />
      </template>
    </template>
  </PrintReportShell>
</template>

<style scoped lang="scss">
.report-h2 {
  letter-spacing: -0.01em;
}

.project-facts {
  margin: 0;
  font-size: 11px;

  &__row {
    display: flex;
    gap: 6px;
  }

  dt {
    opacity: 0.7;
  }

  dd {
    margin: 0;
    font-weight: 600;
  }
}
</style>
