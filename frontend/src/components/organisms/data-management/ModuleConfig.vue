<script setup lang="ts">
import { computed, ref, provide, watch } from 'vue';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import { useModuleConfig } from 'src/composables/useModuleConfig';
import { useRecalculation } from 'src/composables/useRecalculation';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { usePipelineStateStore } from 'src/stores/pipelineState';
import { usePipelineStream } from 'src/composables/usePipelineStream';
import type { PipelineJob, PipelineProgress } from 'src/stores/pipelineStream';
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
}

const props = defineProps<Props>();

const yearConfigStore = useYearConfigStore();
const pipelineStateStore = usePipelineStateStore();

const { getModuleTypeIdFromName, isModuleEnabled, isModuleIncomplete } =
  useModuleConfig({
    module: props.module,
  });

// Plan 310-D / Issue #1062 — pipeline-scoped SSE consumer drives the
// "Recalculating..." badge.  The active pipeline_id lives in the
// unified ``pipelineStateStore`` keyed by ``(module_type_id, year)``
// — the SSE composable is responsible for the live state of that
// pipeline once we know its id.
const {
  subscribe,
  unsubscribe,
  isFinishedFor,
  progressFor,
  hasErrorFor,
  jobsFor,
} = usePipelineStream();

const currentPipelineId = computed<string | null>(() =>
  pipelineStateStore.getPipelineId(
    getModuleTypeIdFromName(props.module),
    yearConfigStore.selectedYear,
  ),
);

async function refreshPipelineState() {
  const moduleTypeId = getModuleTypeIdFromName(props.module);
  // ``getModuleTypeIdFromName`` returns 0 for unknown module names — bail
  // before issuing ``GET /v1/sync/active-pipelines?modules=0`` and polluting
  // the store with a ``0:<year>`` cache key.  Mirrors the falsy-id guard
  // pattern in other useModuleConfig helpers.
  if (!moduleTypeId) return;
  await pipelineStateStore.loadFor(yearConfigStore.selectedYear, [
    moduleTypeId,
  ]);
}

// Initial fetch + re-fetch on year change — the same module can have
// different pipeline state across years (e.g. operator switching
// between report years while a chain runs in the background).
watch(
  () => yearConfigStore.selectedYear,
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

// Issue #1219 — the badge now shows which of the 3 pipeline phases is
// running (Data → Emissions → Aggregation) instead of a bare
// "Recalculating…".  Falls back to the generic label in the brief
// window before the first authoritative ``progress`` payload lands.
const PHASE_LABEL_KEYS: Record<string, string> = {
  data: 'data_management_pipeline_phase_data',
  emissions: 'data_management_pipeline_phase_emissions',
  aggregation: 'data_management_pipeline_phase_aggregation',
};

// Issue #1219 — the module owns the single pipeline SSE subscription;
// expose its authoritative progress to the per-upload cards (provided
// below) so each card shows the live recalc phase, not just whether
// its own upload job is RUNNING.
const pipelineProgress = computed<PipelineProgress | null>(() => {
  const id = currentPipelineId.value;
  return id ? progressFor(id).value : null;
});

const recalcBadgeLabelKey = computed<string>(
  () =>
    (pipelineProgress.value &&
      PHASE_LABEL_KEYS[pipelineProgress.value.phase_label]) ??
    'data_management_pipeline_recalculating',
);

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
  // Hidden in the "start" state where the module is missing required
  // factor (and/or reference) uploads. Without those, the recalc has
  // nothing to compute against — the operator first needs to upload
  // the missing pieces; the recalc button there is a misleading
  // affordance. Issue #1215 — ``isModuleIncomplete`` now reads the
  // backend-computed flag (missing-mandatory only; errored jobs no
  // longer raise it).
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
        yearConfigStore.fetchConfig(yearConfigStore.selectedYear),
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
} = useRecalculation();

const showDataEntryDialog = ref(false);
const dialogCurrentRow = ref<ImportRow | null>(null);
const dialogTargetType = ref<TargetType | null>(null);

const showRecalcDialog = ref(false);
const recalcDialogModuleTypeId = ref<number | null>(null);
const recalcOnlyStale = ref(true);

// Plan 310-D — fix(F-C1): Quasar's ``<q-tooltip>`` is hover-only by
// spec (verified at ``QTooltip.js:247-266`` — only ``mouseenter`` /
// ``mouseleave`` are registered as triggers).  ``tabindex="0"`` alone
// makes the badge focusable but never opens the tooltip for keyboard
// users.  ``PipelineDiagnosticTooltip`` re-exposes Quasar's
// ``show()`` / ``hide()`` via ``defineExpose``; the parent badge
// drives them from ``@focus`` / ``@blur`` so the diagnostic content
// (pipeline UUID, per-job state, status messages) is reachable
// without a mouse.  The copy-pipeline-id button inside the tooltip
// stays mouse-only because the tooltip portal closes on ``blur`` —
// honest partial-a11y; full keyboard reachability would require
// switching primitives (``<q-popup-proxy>`` / ``<q-menu>``) which the
// plan tracks as a future enhancement.
type TooltipExposed = { show: () => void; hide: () => void };
const recalcTooltip = ref<TooltipExposed>();
const failureTooltip = ref<TooltipExposed>();

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
    yearConfigStore.fetchConfig(yearConfigStore.selectedYear),
    refreshPipelineState(),
  ]);
}

async function handleJobProgressing() {
  // No-op since the pipeline-SSE + ``mergeLivePipelineJob`` work
  // (commit 4a5d0c43): the live state of every job in the chain is
  // already delivered through ``livePipelineJobsById`` (provided by
  // this component, consumed by cards) and overlaid onto the row
  // snapshot reactively.  Previously this fired ``fetchConfig`` +
  // ``loadFor`` on every per-job SSE tick (~2s), producing a stream
  // of redundant ``GET /year-configuration/{year}`` and
  // ``GET /sync/active-pipelines?...`` requests during a single
  // upload's phase 1.  The snapshot-only fields (``meta.file_name``,
  // ``meta.rows_processed``) land in the row via ``handleJobCompleted``,
  // which still fires once when the parent reaches FINISHED; the
  // ``isFinishedFor`` watcher below covers the whole-pipeline
  // terminal case.  Kept as a function (not removed) so the
  // provide/inject contract with children stays stable — useful if a
  // future feature actually needs a per-tick hook here.
}

// Live SSE jobs of the in-flight pipeline keyed by ``job_id`` — empty
// map when no pipeline is active.  Cards inject this and prefer the
// live state over their snapshot's ``row.last*Job.state`` so the
// per-row spinner rehydrates after a hard reload (the per-job SSE
// opened by ``useDataEntryDialog`` is in-memory and dies on reload;
// the pipeline SSE re-subscribes on mount via ``currentPipelineId``,
// so its jobs[] payload — which includes the csv_ingest /
// factor_ingest / reference_ingest parent — IS the durable source of
// truth for in-flight upload state.  See ``mergeLivePipelineJob`` in
// ``useModuleConfig.ts``.).
const livePipelineJobsById = computed<ReadonlyMap<number, PipelineJob>>(() => {
  const id = currentPipelineId.value;
  if (!id) return new Map();
  // ``jobsFor`` returns ``PipelineJob[]`` directly (not a ``ComputedRef``)
  // — the reactivity flows through the underlying ``entries[id].jobs``
  // proxy access inside the helper, so this ``computed`` re-runs on
  // every ``applyUpdate``.
  return new Map(jobsFor(id).map((j) => [j.id, j]));
});

provide('openDataEntryDialog', openDataEntryDialog);
provide('getRecalcStatus', yearConfigStore.getRecalcStatus);
provide('handleJobCompleted', handleJobCompleted);
provide('handleJobProgressing', handleJobProgressing);
provide('recalcTypeRunning', recalcTypeRunning);
provide('triggerTypeRecalculation', triggerTypeRecalculation);
provide('pipelineProgress', pipelineProgress);
provide('livePipelineJobsById', livePipelineJobsById);
// Exposed for the abort-pipeline flow: cards / sections that own a
// "Cancel/Abort" button read this to know which pipeline to stop.
// Replaces the legacy per-job cancel (single-job operation went away
// with the pipeline-debug refactor, #1236).
provide('currentPipelineId', currentPipelineId);
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
              Plan 310-D — fix(F-C1): ``tabindex="0"`` + ``aria-label``
              make the badge keyboard-focusable and named for screen
              readers, but Quasar's ``<q-tooltip>`` is hover-only.  The
              child component re-exposes ``show()`` / ``hide()`` via
              ``defineExpose``; the badge drives them from ``@focus`` /
              ``@blur`` so the diagnostic content is reachable without
              a mouse.  See the ref declarations in ``<script setup>``
              for the full rationale.
            -->
            <q-badge
              v-if="isRecalculating"
              outline
              rounded
              color="info"
              class="text-weight-medium cursor-help"
              tabindex="0"
              :aria-label="$t(recalcBadgeLabelKey)"
              :label="$t(recalcBadgeLabelKey)"
              @focus="recalcTooltip?.show()"
              @blur="recalcTooltip?.hide()"
            >
              <PipelineDiagnosticTooltip
                v-if="currentPipelineId"
                ref="recalcTooltip"
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
              @focus="failureTooltip?.show()"
              @blur="failureTooltip?.hide()"
            >
              <PipelineDiagnosticTooltip
                v-if="currentPipelineId"
                ref="failureTooltip"
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

      <ModuleConfigSection :module="module" />

      <ModuleUploadsSection
        :module="module"
        :is-module-enabled="isModuleEnabled(module)"
      >
        <template #submodules>
          <SubmoduleConfig :module="module" />
        </template>
      </ModuleUploadsSection>
    </q-expansion-item>
  </q-card>

  <DataEntryDialog
    v-model="showDataEntryDialog"
    :row="dialogCurrentRow || ({} as ImportRow)"
    :year="yearConfigStore.selectedYear"
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
