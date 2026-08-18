<template>
  <q-page class="page-grid">
    <q-card flat class="container">
      <q-icon
        name="o_display_settings"
        color="info"
        size="32px"
        class="q-mb-md"
      />
      <h1 class="text-h2 q-mb-md">{{ $t('simulation_explore_page_title') }}</h1>
      <p class="text-body1 q-mb-none">
        {{ $t('simulation_explore_page_intro') }}
      </p>
    </q-card>

    <template v-if="ready">
      <q-skeleton
        v-if="!simulatorReady"
        type="rect"
        height="200px"
        class="full-width"
      />
      <q-card v-else flat bordered class="q-pa-none">
        <template v-for="(m, mIdx) in modules" :key="m.type">
          <q-separator v-if="mIdx > 0" />
          <q-expansion-item
            v-model="expandedModules[m.type]"
            header-class="q-py-md"
          >
            <template #header>
              <div class="flex items-center">
                <ModuleIconBox :name="m.type" size="sm" class="q-mr-sm" />
                <div class="text-h5 text-weight-medium">
                  {{ $t(m.type) }}
                </div>
                <q-icon
                  v-if="moduleTooltip(m.type)"
                  :name="outlinedInfo"
                  size="16px"
                  color="grey-6"
                  class="cursor-pointer q-ml-sm"
                  :aria-label="$t('module-info-label')"
                  @click.stop
                >
                  <q-tooltip
                    anchor="center right"
                    self="top right"
                    class="u-tooltip"
                  >
                    {{ moduleTooltip(m.type) }}
                  </q-tooltip>
                </q-icon>
              </div>
            </template>

            <q-separator />

            <template v-if="m.type === MODULES.ResearchFacilities">
              <PlannerResearchFacilityRows
                v-if="carbonReportId != null"
                :carbon-report-id="carbonReportId"
                :factor-year="year"
                hide-budget
                :disable="false"
              />
            </template>
            <template v-else-if="m.type === MODULES.Headcount">
              <p class="text-body2 text-grey-7 q-px-lg q-pt-md q-mb-md">
                {{ $t('simulation_headcount_fte_hint') }}
              </p>
              <PlannerHeadcountRows
                v-if="carbonReportId != null"
                :carbon-report-id="carbonReportId"
                :disable="false"
              />
            </template>
            <div v-else class="q-px-lg q-py-md">
              <div
                v-for="(sub, subIdx) in m.submodules"
                :key="`${m.type}-${sub.id}`"
                :class="{ 'q-mb-md': subIdx < m.submodules.length - 1 }"
              >
                <SubModuleSection
                  :submodule="sub"
                  :module-config="m.config"
                  :module-type="m.type"
                  :disable="false"
                  :is-explorer="true"
                  tooltip-scope="explorer"
                  :submodule-type="sub.type"
                  :data="null"
                  :loading="false"
                  :error="null"
                  :unit-id="unitId"
                  :year="year"
                  :threshold="m.config.threshold || defaultThreshold"
                />
              </div>
            </div>
          </q-expansion-item>
        </template>
      </q-card>
      <q-skeleton
        v-if="!breakdownReady"
        type="rect"
        height="200px"
        class="full-width"
      />
      <q-card v-else flat bordered>
        <div class="q-pt-lg q-px-lg">
          <h2 class="text-h3 text-weight-medium">
            {{ $t('simulation_explore_page_results_title') }}
          </h2>
        </div>

        <q-separator class="q-mt-lg" />

        <!-- Summary numbers. Gapless grid: each block's own padding is the
             only spacing, so its top and bottom read alike (a gap would land
             above every separator but never at the card edges). Still a grid,
             because BigNumber sizes itself against its row. -->
        <div class="results-blocks">
          <BigNumber
            :title="$t('simulation_explore_page_results_total_tonnes_co2eq')"
            :number="`${formatTonnesCO2(totalTonnesCo2eq)}`"
            comparison=""
            color="info"
            compact
            :bordered="false"
          />

          <q-separator />

          <ModuleCarbonFootprintChart
            :breakdown-data="breakdown"
            :bordered="false"
            :enforce-module-activation="false"
          />

          <q-separator />

          <div class="column items-center justify-center q-pa-xl q-gutter-md">
            <h3 class="text-h4 text-weight-medium">
              {{ $t('simulation_explore_page_results_download_title') }}
            </h3>
            <q-btn
              unelevated
              no-caps
              icon="o_download"
              :label="$t('simulation_explore_page_results_download_button')"
              size="md"
              color="info"
              class="text-weight-medium"
              @click="downloadReport"
            />
          </div>
        </div>
      </q-card>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

import ModuleIconBox from 'src/components/atoms/ModuleIconBox.vue';
import PlannerHeadcountRows from 'src/components/organisms/planner/PlannerHeadcountRows.vue';
import PlannerResearchFacilityRows from 'src/components/organisms/planner/PlannerResearchFacilityRows.vue';
import SubModuleSection from 'src/components/organisms/module/SubModuleSection.vue';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import {
  MODULES,
  MODULES_THRESHOLD_TYPES,
  type Module,
  type Threshold,
} from 'src/constant/modules';
import { moduleTooltipKey } from 'src/utils/tooltipScope';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { getExploreModules } from 'src/utils/exploreModules';
import { formatTonnesCO2 } from 'src/utils/number';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';

const router = useRouter();
const route = useRoute();
const { t, locale } = useI18n();

const workspaceStore = useWorkspaceStore();
const yearConfigStore = useYearConfigStore();
const moduleStore = useModuleStore();

function downloadReport() {
  const url = router.resolve({
    name: 'simulation-explore-print',
    params: {
      language: locale.value.split('-')[0],
      unit: route.params.unit,
      year: route.params.year,
    },
  }).href;
  window.open(url, '_blank');
}

// workspaceGuard ensures selectedUnit and selectedYear are always set before
// this route renders. The non-null assertions are safe here; the ready guard
// below prevents the template from rendering if that invariant is ever broken.
const unitId = computed(() => workspaceStore.selectedUnit!.id);
const year = computed(() => workspaceStore.selectedYear!);
const carbonReportId = computed(
  () => workspaceStore.selectedCarbonReport?.id ?? null,
);
const ready = computed(
  () =>
    workspaceStore.selectedUnit != null && workspaceStore.selectedYear != null,
);

const defaultThreshold: Threshold = {
  type: MODULES_THRESHOLD_TYPES[0],
  value: 0,
};

const mountPrimaryCharts = ref(false);
const simulatorReady = ref(false);
// Gates the results card: until the Explorer's own breakdown is fetched, the
// shared store still holds the Calculator's data from the workspace guard.
const breakdownReady = ref(false);

const modules = computed(() => getExploreModules(yearConfigStore.getModule));

function moduleTooltip(module: Module): string {
  return t(moduleTooltipKey('explorer', module));
}

const expandedModules = reactive<Record<string, boolean>>({});

const totalTonnesCo2eq = computed(() => {
  const breakdown = moduleStore.state.emissionBreakdown;
  if (!breakdown) return 0;

  // Keep consistent with the chart (which shows main categories by default).
  const moduleTotal = (breakdown.module_breakdown ?? []).reduce((sum, row) => {
    const rowTotal = (row.emissions ?? []).reduce((rowSum, e) => {
      return rowSum + (typeof e.value === 'number' ? e.value : 0);
    }, 0);
    return sum + rowTotal;
  }, 0);

  return moduleTotal || breakdown.total_tonnes_co2eq || 0;
});

const breakdown = computed(() => moduleStore.state.emissionBreakdown);

async function fetchEmissionBreakdown() {
  const carbonReportId = workspaceStore.selectedCarbonReport?.id;
  if (!carbonReportId) return;
  await moduleStore.getEmissionBreakdown(carbonReportId, []);
}

async function prefetchSubmoduleCounts() {
  // One preview_limit=0 request per module instead of one per submodule.
  // data_entry_types_total_items covers all submodule counts in a single response.
  await moduleStore.prefetchAllModuleCounts(
    modules.value
      .filter(
        (m) =>
          m.type !== MODULES.Headcount && m.type !== MODULES.ResearchFacilities,
      )
      .map((m) => ({
        type: m.type,
        unit: unitId.value,
        year: String(year.value),
      })),
  );
}

onMounted(async () => {
  mountPrimaryCharts.value = true;
  if (unitId.value && year.value) {
    await workspaceStore.selectSimulatorExploreCarbonReport(
      unitId.value,
      year.value,
    );
    // Gate SubModuleSection rendering until the simulator report exists in DB
    // so that module table requests don't 404 before the record is created.
    simulatorReady.value = true;
  }
  await Promise.all([prefetchSubmoduleCounts(), fetchEmissionBreakdown()]);
  breakdownReady.value = true;
});
</script>

<style scoped>
.chart-wrapper {
  height: 600px;
}

.results-blocks {
  display: grid;
  grid-template-columns: 1fr;
}
</style>
