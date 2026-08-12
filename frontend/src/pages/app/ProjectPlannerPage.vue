<template>
  <q-page class="page-grid">
    <q-card v-if="notFound" flat class="container">
      <q-icon
        name="o_calendar_month"
        color="info"
        size="32px"
        class="q-mb-md"
      />
      <h1 class="text-h2 q-mb-md">{{ $t('project_planner_page_title') }}</h1>
      <p class="text-body1 q-mb-md">
        {{ $t('project_planner_not_found') }}
      </p>
      <q-btn
        unelevated
        no-caps
        color="info"
        :label="$t('project_planner_back_home')"
        class="text-weight-medium"
        :to="{ name: 'home' }"
      />
    </q-card>

    <template v-else-if="plan">
      <!-- Title box -->
      <q-card flat class="container">
        <div class="row justify-between items-start no-wrap">
          <div class="col">
            <q-icon name="o_tune" color="info" size="32px" class="q-mb-md" />
            <h1 class="text-h2 q-mb-md">{{ $t('planner_page_title') }}</h1>
            <p class="text-body1 q-mb-sm">
              {{ $t('planner_page_subtitle') }}
            </p>
            <p class="text-body1 q-mb-none">
              {{ $t('planner_page_intro') }}
            </p>
          </div>
          <q-icon
            name="o_info"
            size="sm"
            class="cursor-pointer"
            :aria-label="$t('module-info-label')"
          >
            <q-tooltip anchor="center right" self="top right" class="u-tooltip">
              {{ $t('planner_methodology_tooltip') }}
            </q-tooltip>
          </q-icon>
        </div>
      </q-card>

      <!-- Project information box -->
      <planner-project-info :plan="plan" @updated="onPlanUpdated" />

      <!-- One section per year of the range -->
      <template v-if="plansStore.planYears.length">
        <planner-year-section
          v-for="yearData in plansStore.planYears"
          :key="yearData.id"
          :plan-id="plan.id"
          :year-data="yearData"
          :unit-id="unitId"
          :default-factor-year="plan.default_factor_year"
          :reference-year-options="referenceYearOptions"
          :expanded-keys="expandedKeys"
          :project-years-count="projectYearsCount"
          @toggle-module="onToggleModule"
        />

        <!-- Whole-plan results: every year of the range summed together -->
        <q-card flat bordered>
          <div class="q-pt-lg q-px-lg">
            <h2 class="text-h3 text-weight-medium">
              {{ $t('planner_results_title') }}
            </h2>
          </div>

          <q-separator class="q-mt-lg" />

          <!-- Gapless grid: each block's own padding is the only spacing, so
               its top and bottom read alike (a gap would land above every
               separator but never at the card edges). Still a grid, because
               BigNumber sizes itself against its row. -->
          <div class="results-blocks">
            <!-- Grant results sit beside the year-by-year results, never
                 summed together — the two views count the same project
                 (#1977). -->
            <div
              v-if="plan.is_grant_proposal && hasYearSections"
              class="row items-stretch no-wrap"
            >
              <BigNumber
                class="col"
                :title="grantTotalTitle"
                :number="formatTonnesCO2(grantTotalTonnes)"
                comparison=""
                color="info"
                compact
                :bordered="false"
              />
              <q-separator vertical />
              <BigNumber
                class="col"
                :title="yearsTotalTitle"
                :number="formatTonnesCO2(totalTonnesCo2eq)"
                comparison=""
                color="info"
                compact
                :bordered="false"
              />
            </div>
            <BigNumber
              v-else-if="plan.is_grant_proposal"
              :title="grantTotalTitle"
              :number="formatTonnesCO2(grantTotalTonnes)"
              comparison=""
              color="info"
              compact
              :bordered="false"
            />
            <BigNumber
              v-else
              :title="$t('planner_results_total_tonnes_co2eq')"
              :number="formatTonnesCO2(totalTonnesCo2eq)"
              comparison=""
              color="info"
              compact
              :bordered="false"
            />

            <q-separator />

            <PlannerGrantComparisonChart
              v-if="plan.is_grant_proposal && hasYearSections"
              :title="
                $t('planner_results_comparison_chart_title', {
                  name: plan.name,
                })
              "
              :grant-breakdown="grantBreakdown"
              :years-breakdown="breakdown"
              :grant-year-range="grantYearRange"
              :effective-year-range="effectiveYearRange"
            />
            <ModuleCarbonFootprintChart
              v-else-if="plan.is_grant_proposal"
              :breakdown-data="grantBreakdown"
              :title="
                $t('planner_results_comparison_chart_title', {
                  name: plan.name,
                })
              "
              :bordered="false"
            />
            <ModuleCarbonFootprintChart
              v-else
              :breakdown-data="breakdown"
              :title="$t('planner_results_chart_title', { name: plan.name })"
              :bordered="false"
            />

            <q-separator />

            <div class="column items-center justify-center q-pa-xl q-gutter-md">
              <h3 class="text-h4 text-weight-medium">
                {{ $t('planner_results_download_title') }}
              </h3>
              <q-btn
                unelevated
                no-caps
                icon="o_download"
                :label="$t('planner_results_download_button')"
                size="md"
                color="info"
                class="text-weight-medium"
                @click="downloadReport"
              />
            </div>
          </div>
        </q-card>
      </template>
      <q-card v-else flat bordered class="q-pa-lg">
        <p class="text-body1 q-mb-none text-grey-8">
          {{ $t('planner_no_years_hint') }}
        </p>
      </q-card>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import PlannerGrantComparisonChart from 'src/components/charts/results/PlannerGrantComparisonChart.vue';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import PlannerProjectInfo from 'src/components/organisms/planner/PlannerProjectInfo.vue';
import PlannerYearSection from 'src/components/organisms/planner/PlannerYearSection.vue';
import {
  useSimulatorPlansStore,
  type SimulatorPlan,
} from 'src/stores/simulatorPlans';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { sumBreakdownTonnes } from 'src/utils/breakdownTotal';
import { toEmissionBreakdown } from 'src/utils/emissionStatsAdapter';
import { formatTonnesCO2 } from 'src/utils/number';
import {
  filledYearRange,
  formatYearRange,
  withYearRange,
} from 'src/utils/plannerYearRange';

const route = useRoute();
const router = useRouter();
const { locale, t } = useI18n();
const workspaceStore = useWorkspaceStore();
const plansStore = useSimulatorPlansStore();
const yearConfigStore = useYearConfigStore();

// workspaceGuard ensures selectedUnit is always set before this route renders
// (same invariant as SimulationExplorePage).
const unitId = computed(() => workspaceStore.selectedUnit!.id);

const plan = ref<SimulatorPlan | null>(null);
const notFound = ref(false);
// `${year}-${module}` of every expanded module. Any number can be open at
// once, except the same module in two years: the module store keys its
// submodule rows by submodule id alone, so both would read one another's data.
const expandedKeys = ref<string[]>([]);

function onToggleModule({
  key,
  module,
  open,
}: {
  key: string;
  module: string;
  open: boolean;
}) {
  const others = expandedKeys.value.filter(
    (k) => k !== key && !k.endsWith(`-${module}`),
  );
  expandedKeys.value = open ? [...others, key] : others;
}

// Grant tables multiply per-year kgCO₂eq over the plan's duration (#1979).
const projectYearsCount = computed(() =>
  plan.value?.start_year != null && plan.value?.end_year != null
    ? plan.value.end_year - plan.value.start_year + 1
    : null,
);

const hasYearSections = computed(() =>
  plansStore.planYears.some((y) => !y.is_grant),
);

const breakdown = computed(() =>
  plansStore.aggregateStats
    ? toEmissionBreakdown(plansStore.aggregateStats)
    : null,
);

const grantBreakdown = computed(() =>
  plansStore.grantStats ? toEmissionBreakdown(plansStore.grantStats) : null,
);

const totalTonnesCo2eq = computed(() => sumBreakdownTonnes(breakdown.value));

// The Grant Proposal view spans the whole plan; the effective view spans
// only the years that hold data.
const grantYearRange = computed(() =>
  formatYearRange(plan.value?.start_year, plan.value?.end_year),
);
const effectiveYearRange = computed(() =>
  filledYearRange(plansStore.planYears),
);
const grantTotalTitle = computed(() =>
  withYearRange(t('planner_results_grant_total_title'), grantYearRange.value),
);
const yearsTotalTitle = computed(() =>
  withYearRange(
    t('planner_results_years_total_title'),
    effectiveYearRange.value,
  ),
);

const grantTotalTonnes = computed(() =>
  sumBreakdownTonnes(grantBreakdown.value),
);

function downloadReport() {
  const url = router.resolve({
    name: 'project-planner-print',
    params: {
      language: locale.value.split('-')[0],
      unit: route.params.unit,
      year: route.params.year,
      planId: route.params.planId,
    },
  }).href;
  window.open(url, '_blank');
}

// Reference years are constrained to years open in the Calculator.
const referenceYearOptions = computed(() =>
  [...yearConfigStore.startedYears]
    .sort((a, b) => b - a)
    .map((year) => ({ label: String(year), value: year })),
);

function onPlanUpdated(updated: SimulatorPlan) {
  // Section-affecting updates (year range, grant flag, year sections) are
  // refetched by the store's updatePlan, no extra refetch needed here.
  plan.value = updated;
}

onMounted(async () => {
  try {
    plan.value = await plansStore.getPlan(Number(route.params.planId));
  } catch {
    notFound.value = true;
    return;
  }
  await Promise.all([
    plansStore.fetchPlanYears(plan.value.id),
    plansStore.fetchAggregateStats(plan.value.id),
    yearConfigStore.fetchConfiguredYears(),
  ]);
});

onUnmounted(() => {
  plansStore.clearAggregate();
});
</script>

<style scoped lang="scss">
.results-blocks {
  display: grid;
  grid-template-columns: 1fr;
}
</style>
