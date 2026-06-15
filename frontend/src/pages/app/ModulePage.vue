<template>
  <q-page>
    <div class="module-page">
      <module-title
        :type="currentModuleType"
        :has-description="staticModuleConfig.hasDescription"
        :has-description-subtext="staticModuleConfig.hasDescriptionSubtext"
      />
      <!-- module summary is rendered in the sidebar -->
      <q-card class="container container--pa-none" flat>
        <module-charts :type="currentModuleType" />
      </q-card>
      <!-- module tables iteration -->
      <module-table-section
        v-if="!forbiddenModules.includes(currentModuleType)"
        :type="currentModuleType"
        :data="data"
        :loading="loading"
        :error="error"
        :unit-id="workspaceStore.selectedUnit?.id"
        :year="workspaceStore.selectedYear"
        :disable="timelineStore.canEdit === false"
      />
      <module-navigation :current-module="currentModuleType" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { computed, onMounted, provide, watch, Ref } from 'vue';

import ModuleTitle from 'src/components/organisms/module/ModuleTitle.vue';
import ModuleCharts from 'src/components/organisms/module/ModuleCharts.vue';
import ModuleTableSection from 'src/components/organisms/module/ModuleTableSection.vue';
import ModuleNavigation from 'src/components/organisms/module/ModuleNavigation.vue';
import { Module } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { ModuleConfig } from 'src/constant/moduleConfig';
import { MODULES_CONFIG } from 'src/constant/module-config';
import { getModuleTypeId } from 'src/constant/moduleStates';
import { usePipelineStateStore } from 'src/stores/pipelineState';
import { usePipelineStream } from 'src/composables/usePipelineStream';
const $route = useRoute();
const currentModuleType = computed(() => $route.params.module as Module);
import { useTimelineStore } from 'src/stores/modules';
const timelineStore = useTimelineStore();

const workspaceStore = useWorkspaceStore();

const moduleStore = useModuleStore();
const pipelineStateStore = usePipelineStateStore();
const { subscribe, unsubscribe, progressFor } = usePipelineStream();

const forbiddenModules: Module[] = [];

const staticModuleConfig: Ref<ModuleConfig> = computed(
  () => MODULES_CONFIG[currentModuleType.value] as ModuleConfig,
);

const data = computed(() => moduleStore.state.data);
const loading = computed(() => moduleStore.state.loading);
const error = computed(() => moduleStore.state.error);

// ACTIONS
// get data on mount and when route params change
const getData = () => {
  if (!currentModuleType.value) return;
  if (
    currentModuleType.value &&
    forbiddenModules.includes(currentModuleType.value)
  ) {
    console.warn(
      `ModulePage: No data fetching implemented for module type ${currentModuleType.value}`,
    );
    moduleStore.state.data = null;
    moduleStore.state.loading = false;
    moduleStore.state.error = null;
    return;
  }
  moduleStore.getModuleTotals(
    currentModuleType.value,
    workspaceStore.selectedUnit?.id,
    String(workspaceStore.selectedYear),
  );
};

onMounted(getData);
watch(
  [
    () => currentModuleType.value,
    () => workspaceStore.selectedUnit,
    () => workspaceStore.selectedYear,
  ],
  getData,
);

// Two-phase refresh driven by the bulk pipeline's authoritative
// 3-phase progress (data → emissions → aggregation).  A CSV upload
// (ModuleTable) dispatches a pipeline whose per-row emissions land in
// the `emission_recalc` jobs and whose stats land in the trailing
// `aggregation` job — both AFTER the `csv_ingest` job the upload's
// own single-job SSE watches.  So we watch the whole-pipeline SSE
// here and react per phase:
//
//   * emissions done → refresh the loaded submodules' rows (per-row
//     kg_co2eq is now written) via `moduleStore.refreshLoadedSubmodules`.
//   * aggregation done → refresh module totals + emission breakdown
//     (the charts).
// Both refreshes are driven centrally from the watches below, reacting
// to real pipeline SSE state (no synthetic event bus).
//
// While the pipeline runs, `statsRecalculating` drives a spinner on the
// charts so stale numbers aren't shown silently.  The pipeline_id is
// seeded into `pipelineStateStore` by `initiateSync` on dispatch.
const currentPipelineId = computed<string | null>(() => {
  if (!currentModuleType.value) return null;
  const moduleTypeId = getModuleTypeId(currentModuleType.value);
  const year = workspaceStore.selectedYear;
  if (moduleTypeId == null || year == null) return null;
  return pipelineStateStore.getPipelineId(moduleTypeId, Number(year));
});

const pipelineProgress = computed(() =>
  currentPipelineId.value ? progressFor(currentPipelineId.value).value : null,
);

// Spinner gate for ModuleCharts: an active pipeline that hasn't
// finished and hasn't errored is still computing stats.
const statsRecalculating = computed(() => {
  const p = pipelineProgress.value;
  return !!currentPipelineId.value && !!p && !p.done && !p.has_error;
});
provide('moduleStatsRecalculating', statsRecalculating);

// Submodule types of the module currently in view (for the row refresh).
const submoduleTypes = computed<string[]>(() =>
  (staticModuleConfig.value?.submodules ?? []).map((sub) => sub.type as string),
);

// Subscribe/unsubscribe as the active pipeline_id transitions
// (null → uuid on upload, uuidA → uuidB on a second upload).
let lastSubscribedId: string | null = null;
watch(
  currentPipelineId,
  async (next) => {
    if (lastSubscribedId === next) return;
    if (lastSubscribedId) unsubscribe(lastSubscribedId);
    lastSubscribedId = next;
    if (next) await subscribe(next);
  },
  { immediate: true },
);

// Event 1 — emissions ready: phase advanced past `emissions`
// (`aggregation` or `done`).  Refresh the loaded submodules' rows so
// per-row kg_co2eq reflects the freshly computed emissions.
watch(
  () => {
    const p = pipelineProgress.value;
    if (!p) return false;
    return p.done || p.phase_label === 'aggregation';
  },
  (ready, wasReady) => {
    const unit = workspaceStore.selectedUnit?.id;
    if (ready && !wasReady && currentModuleType.value && unit != null) {
      void moduleStore.refreshLoadedSubmodules(
        currentModuleType.value,
        unit,
        String(workspaceStore.selectedYear),
        submoduleTypes.value,
      );
    }
  },
);

// Event 2 — stats ready: whole pipeline done (aggregation wrote
// `carbon_reports.stats`).  Refresh module totals (headcount chart
// reads `state.data.stats`) and bust the emission-breakdown cache so
// ModuleCharts re-fetches `.../emission-breakdown`.
watch(
  () => pipelineProgress.value?.done === true,
  (done, wasDone) => {
    if (done && !wasDone) {
      getData();
      void moduleStore.refreshEmissionBreakdownIfNeeded();
    }
  },
);
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;
.module-page {
  padding-top: tokens.$template-padding-y;
  padding-bottom: tokens.$template-padding-y;
  display: grid;
  grid-auto-flow: row;
  row-gap: tokens.$template-gap;
  align-items: start;
  grid-auto-rows: max-content;
  width: 100%;

  // center the page
  justify-self: center; // center within the parent grid cell
}
</style>
