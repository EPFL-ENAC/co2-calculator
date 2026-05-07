<script setup lang="ts">
import { computed, ref, provide, watch } from 'vue';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import { useModuleConfig } from 'src/composables/useModuleConfig';
import { useRecalculation } from 'src/composables/useRecalculation';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { usePipelineStateStore } from 'src/stores/pipelineState';
import { usePipelineStream } from 'src/composables/usePipelineStream';
import {
  TargetType,
  type ImportRow,
} from 'src/stores/backofficeDataManagement';
import DataEntryDialog from 'src/components/organisms/data-management/DataEntryDialog.vue';
import ModuleRecalculationDialog from 'src/components/molecules/data-management/ModuleRecalculationDialog.vue';
import ModuleConfigSection from 'src/components/molecules/data-management/ModuleConfigSection.vue';
import ModuleUploadsSection from 'src/components/molecules/data-management/ModuleUploadsSection.vue';
import PipelineDiagnosticTooltip from 'src/components/molecules/data-management/PipelineDiagnosticTooltip.vue';
import SubmoduleConfig from 'src/components/organisms/data-management/SubmoduleConfig.vue';

interface Props {
  module: string;
  selectedYear: number;
}

const props = defineProps<Props>();

const yearConfigStore = useYearConfigStore();
const pipelineStateStore = usePipelineStateStore();

const { getModuleTypeIdFromName, isModuleEnabled, isModuleIncomplete } =
  useModuleConfig({
    module: props.module,
    selectedYear: props.selectedYear,
  });

// Plan 310-D / Issue #1062 — pipeline-scoped SSE consumer drives the
// "Recalculating..." badge.  The active pipeline_id lives in the
// unified ``pipelineStateStore`` keyed by ``(module_type_id, year)``
// — the SSE composable is responsible for the live state of that
// pipeline once we know its id.
const { subscribe, unsubscribe, isFinishedFor, hasErrorFor } =
  usePipelineStream();

const currentPipelineId = computed<string | null>(() =>
  pipelineStateStore.getPipelineId(
    getModuleTypeIdFromName(props.module),
    props.selectedYear,
  ),
);

async function refreshPipelineState() {
  const moduleTypeId = getModuleTypeIdFromName(props.module);
  await pipelineStateStore.loadFor(props.selectedYear, [moduleTypeId]);
}

// Initial fetch + re-fetch on year change — the same module can have
// different pipeline state across years (e.g. operator switching
// between report years while a chain runs in the background).
watch(
  () => props.selectedYear,
  () => {
    void refreshPipelineState();
  },
  { immediate: true },
);

const isRecalculating = computed<boolean>(() => {
  const id = currentPipelineId.value;
  if (!id) return false;
  // Active until the SSE stream signals finish — the watch below
  // refetches the active-pipelines store on completion so the id
  // clears and the badge disappears.
  return !isFinishedFor(id).value;
});

const hasRecalcFailure = computed<boolean>(() => {
  const id = currentPipelineId.value;
  if (!id) return false;
  return hasErrorFor(id).value;
});

// Plan 310-D — contextual recalculation button.
//
// Old behavior: always visible when ``needs_recalculation`` was true,
// even while a chain was in flight (redundant — the chain auto-fires
// on upload and the badge shows progress).
//
// New behavior: visible only when there's something for the operator
// to act on — either (a) the chain failed and they want to retry, or
// (b) staleness was detected and no chain is running to clear it.
// Hidden during active recalc (the badge says it all) and on a clean
// module (nothing to do).
const moduleNeedsRecalculation = computed<boolean>(
  () =>
    !!yearConfigStore.recalculationStatus[getModuleTypeIdFromName(props.module)]
      ?.needs_recalculation,
);

const showRecalcButton = computed<boolean>(() => {
  // Hidden during active recalc — the badge says it all.
  if (isRecalculating.value) return false;
  // Hidden in the "start" state where the module is missing
  // required factors and/or data uploads.  Without those, the
  // recalc has nothing to compute against — the operator first
  // needs to upload the missing pieces; the recalc button there
  // is a misleading affordance.  ``isModuleIncomplete`` already
  // tracks "any required factor/data job is missing or errored"
  // for the badge above; reuse it to keep the two consistent.
  if (isModuleIncomplete(props.module)) return false;
  return hasRecalcFailure.value || moduleNeedsRecalculation.value;
});

const recalcButtonLabel = computed<string>(() =>
  hasRecalcFailure.value
    ? 'data_management_recalculate_retry'
    : 'data_management_recalculate_emissions',
);

// Wire the SSE subscription to the reactive pipeline_id.  When it
// transitions ``null → uuid`` we subscribe; ``uuid → null`` (badge
// cleared by the year-config refetch) → unsubscribe; ``uuidA →
// uuidB`` (rare — new pipeline started while old finished) → switch.
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

// When the pipeline reports finished, refetch the active-pipelines
// store so the badge clears (or, on error, the entry stays set so the
// retry-button affordance remains).  Also refetch the year config so
// ``recalculation_status.needs_recalculation`` updates.
watch(
  () =>
    currentPipelineId.value
      ? isFinishedFor(currentPipelineId.value).value
      : false,
  async (finished, wasFinished) => {
    if (finished && !wasFinished && !hasRecalcFailure.value) {
      await Promise.all([
        refreshPipelineState(),
        yearConfigStore.fetchConfig(props.selectedYear),
      ]);
    }
  },
);

const {
  recalcRunning,
  recalcTypeRunning,
  confirmModuleRecalculation,
  triggerTypeRecalculation,
  staleTypesForModule,
} = useRecalculation({
  selectedYear: props.selectedYear,
});

const showDataEntryDialog = ref(false);
const dialogCurrentRow = ref<ImportRow | null>(null);
const dialogTargetType = ref<TargetType | null>(null);

const showRecalcDialog = ref(false);
const recalcDialogModuleTypeId = ref<number | null>(null);
const recalcOnlyStale = ref(true);

function openDataEntryDialog(row: ImportRow, targetType: TargetType | null) {
  dialogCurrentRow.value = row;
  dialogTargetType.value = targetType;
  showDataEntryDialog.value = true;
}

function openRecalcDialog(moduleTypeId: number) {
  recalcDialogModuleTypeId.value = moduleTypeId;
  recalcOnlyStale.value = true;
  showRecalcDialog.value = true;
}

async function handleJobCompleted() {
  await Promise.all([
    yearConfigStore.fetchConfig(props.selectedYear),
    refreshPipelineState(),
  ]);
}

async function handleJobProgressing() {
  await Promise.all([
    yearConfigStore.fetchConfig(props.selectedYear),
    refreshPipelineState(),
  ]);
}

provide('openDataEntryDialog', openDataEntryDialog);
provide('getRecalcStatus', yearConfigStore.getRecalcStatus);
provide('handleJobCompleted', handleJobCompleted);
provide('handleJobProgressing', handleJobProgressing);
provide('recalcTypeRunning', recalcTypeRunning);
provide('triggerTypeRecalculation', triggerTypeRecalculation);
</script>

<template>
  <q-card flat bordered class="q-pa-none q-mb-lg">
    <q-expansion-item expand-separator>
      <template #header>
        <q-item-section avatar>
          <ModuleIcon :name="module" size="md" color="accent" />
        </q-item-section>
        <q-item-section>
          <div class="row items-center q-gutter-sm">
            <span class="text-h4 text-weight-medium">{{ $t(module) }}</span>
            <q-badge
              v-if="!isModuleEnabled(module)"
              outline
              rounded
              color="grey"
              class="text-weight-medium"
              :label="$t('common_disabled')"
            />
            <q-badge
              v-else-if="isModuleIncomplete(module)"
              outline
              rounded
              color="accent"
              class="text-weight-medium"
              :label="$t('common_filter_incomplete')"
            />
            <q-badge
              v-if="
                yearConfigStore.recalculationStatus[
                  getModuleTypeIdFromName(module)
                ]?.needs_recalculation
              "
              outline
              rounded
              color="warning"
              class="text-weight-medium"
              :label="$t('data_management_recalculation_needed')"
            />
            <!--
              Plan 310-D — "Recalculating..." badge for in-flight bulk
              pipelines.  Drives off ``current_pipeline_id`` on the
              per-module recalc-status entry (set when an active
              NOT_STARTED/QUEUED/RUNNING aggregation pipeline touches
              this module's year), with the SSE composable controlling
              the live state.
            -->
            <!--
              Plan 310-D — ``tabindex="0"`` + ``aria-label`` make the
              badge keyboard-focusable so the diagnostic tooltip
              opens on focus (and the copy-pipeline-id button inside
              becomes reachable).  Without these, keyboard-only users
              can't see what the badge promises to surface.
            -->
            <q-badge
              v-if="isRecalculating"
              outline
              rounded
              color="info"
              class="text-weight-medium cursor-help"
              tabindex="0"
              :aria-label="$t('data_management_pipeline_recalculating')"
              :label="$t('data_management_pipeline_recalculating')"
            >
              <PipelineDiagnosticTooltip
                v-if="currentPipelineId"
                :pipeline-id="currentPipelineId"
              />
            </q-badge>
            <q-badge
              v-else-if="hasRecalcFailure"
              outline
              rounded
              color="negative"
              class="text-weight-medium cursor-help"
              tabindex="0"
              :aria-label="$t('data_management_pipeline_failed')"
              :label="$t('data_management_pipeline_failed')"
            >
              <PipelineDiagnosticTooltip
                v-if="currentPipelineId"
                :pipeline-id="currentPipelineId"
              />
            </q-badge>
          </div>
        </q-item-section>
        <q-item-section side>
          <div class="row items-center q-gutter-sm">
            <q-spinner-rings
              v-if="recalcRunning[getModuleTypeIdFromName(module)]"
              color="grey"
              size="sm"
            />
            <!--
              Plan 310-D — contextual recalc button.  Hidden during
              active recalc (badge handles it), visible as "Retry"
              when the last chain failed, visible as "Recalculate"
              when staleness exists without an in-flight chain.
            -->
            <q-btn
              v-if="showRecalcButton"
              flat
              dense
              size="sm"
              icon="refresh"
              :color="hasRecalcFailure ? 'negative' : 'accent'"
              :label="$t(recalcButtonLabel)"
              @click.stop="openRecalcDialog(getModuleTypeIdFromName(module))"
            />
          </div>
        </q-item-section>
      </template>

      <ModuleConfigSection :module="module" :selected-year="selectedYear" />

      <ModuleUploadsSection
        :module="module"
        :selected-year="selectedYear"
        :is-module-enabled="isModuleEnabled(module)"
      >
        <template #submodules>
          <SubmoduleConfig :module="module" :selected-year="selectedYear" />
        </template>
      </ModuleUploadsSection>
    </q-expansion-item>
  </q-card>

  <DataEntryDialog
    v-model="showDataEntryDialog"
    :row="dialogCurrentRow || ({} as ImportRow)"
    :year="selectedYear"
    :target-type="dialogTargetType ?? TargetType.DATA_ENTRIES"
    @completed="handleJobCompleted"
    @progressing="handleJobProgressing"
  />

  <ModuleRecalculationDialog
    v-model="showRecalcDialog"
    :module-type-id="recalcDialogModuleTypeId"
    :stale-types="staleTypesForModule(recalcDialogModuleTypeId || 0)"
    :only-stale="recalcOnlyStale"
    @confirm="confirmModuleRecalculation(recalcDialogModuleTypeId!)"
    @cancel="showRecalcDialog = false"
  />
</template>

<style scoped></style>
