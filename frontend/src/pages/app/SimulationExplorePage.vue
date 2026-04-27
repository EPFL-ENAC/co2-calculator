<template>
  <q-page class="page-grid">
    <q-card flat class="container">
      <q-icon
        name="o_display_settings"
        color="accent"
        size="32px"
        class="q-mb-md"
      />
      <h1 class="text-h2 q-mb-md">{{ $t('simulation_explore_page_title') }}</h1>
      <p class="text-body1 q-mb-none">
        {{ $t('simulation_explore_page_intro') }}
      </p>
    </q-card>

    <q-list>
      <div
        v-for="(m, mIdx) in modules"
        :key="m.type"
        :class="{ 'q-mb-md': mIdx < modules.length - 1 }"
      >
        <q-expansion-item
          v-model="expandedModules[m.type]"
          flat
          header-class="text-h4 text-weight-medium"
          class="container container--pa-none"
        >
          <template #header>
            <div class="row items-center full-width q-gutter-sm">
              <ModuleIcon
                :name="m.type"
                color="accent"
                size="md"
                :aria-label="$t('module-info-label')"
              />
              <div class="col">
                {{ $t(m.type) }}
              </div>
            </div>
          </template>

          <q-separator />

          <q-card-section class="q-pa-none q-mt-md">
            <div class="q-px-lg q-py-sm">
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
                  :submodule-type="sub.type as any"
                  :data="null"
                  :loading="false"
                  :error="null"
                  :unit-id="unitId"
                  :year="year"
                  :threshold="m.config.threshold || defaultThreshold"
                />
              </div>
            </div>
          </q-card-section>
        </q-expansion-item>
      </div>
    </q-list>
    <q-card flat bordered>
      <div class="q-pt-lg q-px-lg">
        <h2 class="text-h3 text-weight-medium">
          {{ $t('simulation_explore_page_results_title') }}
        </h2>
      </div>

      <q-separator class="q-mt-xl" />

      <!-- Summary numbers -->
      <q-card flat class="grid-1-col q-mt-lg q-mb-lg q-px-lg">
        <BigNumber
          :title="$t('simulation_explore_page_results_total_tonnes_co2eq')"
          :number="`${formatTonnesCO2(0)}`"
          comparison=""
          color="accent"
        />
        <template v-if="mountPrimaryCharts">
          <ModuleCarbonFootprintChart
            :breakdown-data="moduleStore.state.emissionBreakdown"
          />
        </template>
        <q-skeleton v-else type="rect" height="360px" class="full-width" />

        <q-card
          flat
          class="container q-pa-xl column items-center justify-center q-gutter-lg"
        >
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
          />
        </q-card>
      </q-card>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import SubModuleSection from 'src/components/organisms/module/SubModuleSection.vue';
import { MODULES_CONFIG } from 'src/constant/module-config';
import type { ModuleConfig } from 'src/constant/moduleConfig';
import { MODULES_THRESHOLD_TYPES, type Threshold } from 'src/constant/modules';
import { MODULES_ORDER } from 'src/constant/timelineItems';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { formatTonnesCO2 } from 'src/utils/number';
import BigNumber from 'src/components/molecules/BigNumber.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';

const workspaceStore = useWorkspaceStore();
const yearConfigStore = useYearConfigStore();
const moduleStore = useModuleStore();

const unitId = computed(() => workspaceStore.selectedUnit?.id ?? null);
const year = computed(() => workspaceStore.selectedYear ?? null);

const defaultThreshold: Threshold = {
  type: MODULES_THRESHOLD_TYPES[0],
  value: 0,
};

const mountPrimaryCharts = ref(false);

const modules = computed(() => {
  return MODULES_ORDER.map((type) => {
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
  }).filter((m): m is NonNullable<typeof m> => m !== null);
});

const expandedModules = reactive<Record<string, boolean>>({});

async function fetchEmissionBreakdown() {
  const carbonReportId = workspaceStore.selectedCarbonReport?.id;
  if (!carbonReportId) return;
  await moduleStore.getEmissionBreakdown(carbonReportId, []);
}

onMounted(async () => {
  mountPrimaryCharts.value = true;
  await fetchEmissionBreakdown();
});
</script>
