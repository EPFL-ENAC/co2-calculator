<template>
  <q-card flat bordered class="q-pa-none">
    <template v-for="(m, mIdx) in modules" :key="m.type">
      <q-separator v-if="mIdx > 0" />
      <q-expansion-item
        :model-value="expandedModules[m.type]"
        header-class="q-py-md"
        @update:model-value="onToggle(m, $event)"
      >
        <template #header>
          <div class="flex items-center">
            <ModuleIconBox :name="m.type" size="sm" class="q-mr-sm" />
            <!-- Testid sits on the title, not the header row: the row also
                 wraps the info icon (@click.stop below), so a click centered
                 on the wider wrapper can land there instead and never
                 reach QExpansionItem's own toggle handler. -->
            <div
              class="text-h5 text-weight-medium"
              :data-testid="`explore-module-title-${m.type}`"
            >
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

        <!-- Content mounts once, on first open, and stays mounted afterwards
             (#2360): QExpansionItem itself keeps its slot in the DOM even
             while collapsed, so without this gate every module's requests
             fire on page mount instead of on demand. -->
        <template v-if="openedModules[m.type]">
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
        </template>
      </q-expansion-item>
    </template>
  </q-card>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import ModuleIconBox from '@/components/atoms/ModuleIconBox.vue';
import PlannerHeadcountRows from '@/components/organisms/planner/PlannerHeadcountRows.vue';
import PlannerResearchFacilityRows from '@/components/organisms/planner/PlannerResearchFacilityRows.vue';
import SubModuleSection from '@/components/organisms/module/SubModuleSection.vue';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import {
  MODULES,
  MODULES_THRESHOLD_TYPES,
  type Module,
  type Threshold,
} from '@/constant/modules';
import { moduleTooltipKey } from '@/utils/tooltipScope';
import { getModuleTypeId } from '@/constant/moduleStates';
import { useModuleStore } from '@/stores/modules';
import { usePipelineStateStore } from '@/stores/pipelineState';
import { usePipelineStream } from '@/composables/usePipelineStream';
import type { ExploreModule } from '@/utils/exploreModules';

const props = defineProps<{
  modules: ExploreModule[];
  unitId: number;
  year: number;
  carbonReportId: number | null;
}>();

const { t } = useI18n();
const moduleStore = useModuleStore();
const pipelineStateStore = usePipelineStateStore();
const { subscribe, unsubscribe, progressFor } = usePipelineStream();

const defaultThreshold: Threshold = {
  type: MODULES_THRESHOLD_TYPES[0],
  value: 0,
};

const expandedModules = reactive<Record<string, boolean>>({});
const openedModules = reactive<Record<string, boolean>>({});

function moduleTooltip(module: Module): string {
  return t(moduleTooltipKey('explorer', module));
}

function onToggle(m: ExploreModule, isOpen: boolean) {
  expandedModules[m.type] = isOpen;
  if (!isOpen || openedModules[m.type]) return;
  openedModules[m.type] = true;

  // Headcount and ResearchFacilities have no submodule-count prefetch today
  // (their rows components fetch their own data once mounted).
  if (m.type === MODULES.Headcount || m.type === MODULES.ResearchFacilities) {
    return;
  }
  void moduleStore.prefetchAllModuleCounts([
    { type: m.type, unit: props.unitId, year: String(props.year) },
  ]);
}

// A CSV upload (ModuleTable) dispatches a 3-phase pipeline (data →
// emissions → aggregation). The upload's own single-job SSE only covers
// the csv_ingest job, so per-row kg_co2eq and the aggregated stats are
// written AFTER its "completed" refresh already ran. As on ModulePage,
// watch the whole-pipeline SSE per module and refresh once each phase
// actually finishes.
const activePipelineIds = computed<Record<string, string | null>>(() => {
  const ids: Record<string, string | null> = {};
  for (const m of props.modules) {
    const moduleTypeId = getModuleTypeId(m.type);
    ids[m.type] =
      moduleTypeId == null
        ? null
        : pipelineStateStore.getPipelineId(moduleTypeId, props.year);
  }
  return ids;
});

// Subscribe/unsubscribe as a module's active pipeline_id transitions
// (null → uuid on upload, uuidA → uuidB on a second upload).
const lastSubscribedIds: Record<string, string | null> = {};
watch(
  activePipelineIds,
  async (next) => {
    for (const [moduleType, id] of Object.entries(next)) {
      const prev = lastSubscribedIds[moduleType] ?? null;
      if (prev === id) continue;
      if (prev) unsubscribe(prev);
      lastSubscribedIds[moduleType] = id;
      if (id) await subscribe(id);
    }
  },
  { immediate: true },
);

// Emissions phase done: per-row kg_co2eq is now written — refresh the
// loaded submodules' rows, preserving pagination/sort/filter.
const emissionsReady = computed<Record<string, boolean>>(() => {
  const ready: Record<string, boolean> = {};
  for (const [moduleType, id] of Object.entries(activePipelineIds.value)) {
    const p = id ? progressFor(id).value : null;
    ready[moduleType] = !!p && (p.done || p.phase_label === 'aggregation');
  }
  return ready;
});
watch(emissionsReady, (next, wasReady) => {
  for (const m of props.modules) {
    if (next[m.type] && !wasReady?.[m.type]) {
      void moduleStore.refreshLoadedSubmodules(
        m.type,
        props.unitId,
        String(props.year),
        m.submodules.map((sub) => sub.id),
      );
    }
  }
});

// Whole pipeline done: aggregation wrote the report stats — refresh the
// submodule title counts and the results card's breakdown/total.
const pipelineDone = computed<Record<string, boolean>>(() => {
  const done: Record<string, boolean> = {};
  for (const [moduleType, id] of Object.entries(activePipelineIds.value)) {
    done[moduleType] = id ? progressFor(id).value?.done === true : false;
  }
  return done;
});
watch(pipelineDone, (next, wasDone) => {
  for (const m of props.modules) {
    if (next[m.type] && !wasDone?.[m.type]) {
      void moduleStore.prefetchAllModuleCounts([
        { type: m.type, unit: props.unitId, year: String(props.year) },
      ]);
      void moduleStore.refreshEmissionBreakdownIfNeeded();
    }
  }
});
</script>
