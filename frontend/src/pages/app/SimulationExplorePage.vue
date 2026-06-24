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
              </div>
            </template>

            <q-separator />

            <div class="q-px-lg q-py-md">
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
                  :is-simulator="true"
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
      <q-card flat bordered>
        <div class="q-pt-lg q-px-lg">
          <h2 class="text-h3 text-weight-medium">
            {{ $t('simulation_explore_page_results_title') }}
          </h2>
        </div>

        <q-separator class="q-mt-xl" />

        <!-- Summary numbers -->
        <div class="grid-1-col q-mt-lg q-mb-lg">
          <BigNumber
            :title="$t('simulation_explore_page_results_total_tonnes_co2eq')"
            :number="`${formatTonnesCO2(totalTonnesCo2eq)}`"
            comparison=""
            color="info"
            :bordered="false"
          />
          <q-separator />
          <ModuleCarbonFootprintChart
            :breakdown-data="filteredBreakdown"
            :bordered="false"
          />

          <q-separator />

          <div class="column items-center justify-center q-pa-xl q-gutter-lg">
            <h3 class="text-h4 text-weight-medium">
              {{ $t('simulation_explore_page_results_download_title') }}
            </h3>
            <q-btn
              unelevated
              no-caps
              icon="o_download"
              :label="$t('simulation_explore_page_results_download_button')"
              size="md"
              color="accent"
              class="text-weight-medium"
              @click="downloadReport"
            />
          </div>
        </div>

        <q-separator />

        <div
          class="row no-wrap items-center justify-center q-pa-xl"
          style="gap: 24px"
        >
          <q-icon name="o_calendar_month" color="accent" size="md" />
          <div class="col">
            <div class="text-h5 text-weight-medium q-mb-xs">
              {{ $t('simulation_explore_page_convert_to_plan_title') }}
            </div>
            <div class="text-body2 text-secondary">
              {{ $t('simulation_explore_page_convert_to_plan_description') }}
            </div>
          </div>
          <q-btn
            unelevated
            no-caps
            :label="$t('simulation_explore_page_convert_to_plan_button')"
            color="info"
            class="text-weight-medium"
          />
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
import SubModuleSection from 'src/components/organisms/module/SubModuleSection.vue';
import { MODULES_CONFIG } from 'src/constant/module-config';
import type { ModuleConfig } from 'src/constant/moduleConfig';
import {
  MODULES,
  MODULES_THRESHOLD_TYPES,
  type Threshold,
} from 'src/constant/modules';
import { MODULES_ORDER } from 'src/constant/timelineItems';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { formatTonnesCO2 } from 'src/utils/number';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';

const router = useRouter();
const route = useRoute();
const { locale } = useI18n();

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

// validateUnitGuard ensures selectedUnit and selectedYear are always set before
// this route renders. The non-null assertions are safe here; the ready guard
// below prevents the template from rendering if that invariant is ever broken.
const unitId = computed(() => workspaceStore.selectedUnit!.id);
const year = computed(() => workspaceStore.selectedYear!);
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

const modules = computed(() => {
  return MODULES_ORDER.filter((type) => type !== MODULES.ResearchFacilities)
    .map((type) => {
      const config = MODULES_CONFIG[type] as ModuleConfig | undefined;
      if (!config?.submodules?.length) return null;

      const unifiedConfig = yearConfigStore.getModule(type);
      const visibleSubmodules = unifiedConfig
        ? config.submodules.filter(
            (sub) => unifiedConfig.submodules[sub.id]?.enabled ?? true,
          )
        : config.submodules;

      if (!visibleSubmodules.length) return null;

      return {
        type,
        config,
        submodules: visibleSubmodules,
      };
    })
    .filter((m): m is NonNullable<typeof m> => m !== null);
});

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

const filteredBreakdown = computed(() => {
  const bd = moduleStore.state.emissionBreakdown;
  if (!bd) return bd;
  return {
    ...bd,
    module_breakdown: bd.module_breakdown.filter(
      (entry) => entry.category !== 'research_facilities',
    ),
  };
});

async function fetchEmissionBreakdown() {
  const carbonReportId = workspaceStore.selectedCarbonReport?.id;
  if (!carbonReportId) return;
  await moduleStore.getEmissionBreakdown(carbonReportId, []);
}

async function prefetchSubmoduleCounts() {
  // One preview_limit=0 request per module instead of one per submodule.
  // data_entry_types_total_items covers all submodule counts in a single response.
  await moduleStore.prefetchAllModuleCounts(
    modules.value.map((m) => ({
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
  await prefetchSubmoduleCounts();
  await fetchEmissionBreakdown();
});
</script>

<style scoped>
.chart-wrapper {
  height: 600px;
}
</style>
