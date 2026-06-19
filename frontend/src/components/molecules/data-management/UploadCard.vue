<script setup lang="ts">
import { computed, inject, type ComputedRef } from 'vue';
import { matCalculate, matCancel, matInfo } from '@quasar/extras/material-icons';
import { outlinedDownload } from '@quasar/extras/material-icons-outlined';
import { useUploadCard } from 'src/composables/useUploadCard';
import {
  TargetType,
  IngestionState,
  IngestionMethod,
} from 'src/stores/backofficeDataManagement';
import type {
  ImportRow,
  SyncJobResponse,
} from 'src/stores/backofficeDataManagement';
import type { RecalculationStatusEntry } from 'src/stores/yearConfig';
import type { PipelineJob, PipelineProgress } from 'src/stores/pipelineStream';

interface Props {
  title: string;
  description: string;
  showMandatoryIndicator?: boolean;
  descriptionSubtext?: string;
  buttonColor: string;
  buttonLabel: string;
  buttonIcon?: string;
  isDisabled?: boolean;
  isLoading?: boolean;
  lastJob?: SyncJobResponse;
  apiJob?: SyncJobResponse;
  targetType?: TargetType;
  hasRecalcButton?: boolean;
  recalcStatus?: RecalculationStatusEntry;
  recalcRunning?: boolean;
  /** Issue #1219 — module-scoped pipeline progress (null when idle). */
  pipelineProgress?: PipelineProgress | null;
  hasComputedFactorButton?: boolean;
  computedFactorRunning?: boolean;
  isComputedFactorDisabled?: boolean;
  row?: ImportRow;
}

const props = withDefaults(defineProps<Props>(), {
  showMandatoryIndicator: false,
  descriptionSubtext: undefined,
  buttonIcon: 'add',
  isDisabled: false,
  isLoading: false,
  lastJob: undefined,
  apiJob: undefined,
  targetType: undefined,
  hasRecalcButton: false,
  recalcStatus: undefined,
  recalcRunning: false,
  pipelineProgress: null,
  hasComputedFactorButton: false,
  computedFactorRunning: false,
  isComputedFactorDisabled: false,
  row: undefined,
});

const emit = defineEmits<{
  (e: 'upload', row: ImportRow, targetType: TargetType): void;
  (e: 'download', row: ImportRow, targetType: TargetType): void;
  (e: 'recalculate', item: ImportRow): void;
  (e: 'compute-factors', item: ImportRow): void;
  // Stops the whole pipeline this card is bound to (replaces the
  // legacy per-job ``cancel`` — see backofficeDataManagement.abortPipeline
  // for the why).  Parent resolves the pipeline_id via inject.
  (e: 'abort'): void;
}>();

const { cardStyle, getJobInfo, hasErrorOrWarning, getErrorDetails } =
  useUploadCard();

const jobInfo = computed(() => getJobInfo(props.lastJob));
const hasErrorOrWarn = computed(() => hasErrorOrWarning(props.lastJob));
const errorDetails = computed(() => getErrorDetails(props.lastJob));
const isJobStuck = computed(
  () =>
    props.lastJob?.state === IngestionState.RUNNING ||
    props.lastJob?.state === IngestionState.QUEUED,
);

const apiJobInfo = computed(() => getJobInfo(props.apiJob));
const hasApiErrorOrWarn = computed(() => hasErrorOrWarning(props.apiJob));
const apiErrorDetails = computed(() => getErrorDetails(props.apiJob));

// Issue #1219 — live recalc-pipeline phase for this card.
//
// Pipeline progress is module-scoped (provided by ModuleConfig as the
// single SSE subscriber) AND kind-scoped: a factor_ingest pipeline
// shouldn't surface its phase on the data card and vice versa.
// ``pipelineAppliesToCard`` gates rendering on ``progress.kind``
// matching this card's ``targetType`` — empty kind (orphan / unknown
// root) falls back to "don't render" rather than risk showing on the
// wrong card.
const PIPELINE_PHASE_LABEL_KEYS: Record<string, string> = {
  data: 'data_management_pipeline_phase_data',
  emissions: 'data_management_pipeline_phase_emissions',
  aggregation: 'data_management_pipeline_phase_aggregation',
};

const TARGET_TO_KINDS: Record<number, ReadonlyArray<string>> = {
  // TargetType.DATA_ENTRIES = 0 — every pipeline whose work targets
  // the data-entries domain belongs on the data card:
  //   * csv_ingest / api_ingest — user uploads or admin sync.
  //   * emission_recalc / module_emission_recalc — pipelines minted by
  //     POST /sync/recalculate-emissions/{module}[/{det}] when the
  //     operator clicks the "Recalculate" button on the data card.
  //     Their kind is set at the parent's ensure_pipeline_exists call
  //     in data_sync.py:1610 + :1710.  Without these the recalc
  //     pipeline runs but the data card stays blank — confusing
  //     because the button that triggered it IS on the data card.
  [TargetType.DATA_ENTRIES]: [
    'csv_ingest',
    'api_ingest',
    'emission_recalc',
    'module_emission_recalc',
  ],
  // TargetType.FACTORS = 1 — the parent is always factor_ingest.
  [TargetType.FACTORS]: ['factor_ingest'],
  // TargetType.REFERENCE_DATA = 3 — reference uploads (building rooms,
  // travel reference) chain through reference_ingest.
  [TargetType.REFERENCE_DATA]: ['reference_ingest'],
};

// Dets actually present in the live pipeline (provided by ModuleConfig
// as ``livePipelineJobsById``).  A single-submodule upload recalcs only
// its own det, so its sibling submodule cards must NOT show the
// emissions/aggregation phase.  Module-wide uploads fan out a recalc
// per det, so every det lands here and all cards light up — both
// correct.  Empty when no pipeline is active or this card renders
// outside ModuleConfig (fixtures), which disables det-scoping below.
const livePipelineJobsById = inject<
  ComputedRef<ReadonlyMap<number, PipelineJob>>
>(
  'livePipelineJobsById',
  computed(() => new Map()),
);

const pipelineDataEntryTypeIds = computed<Set<number>>(() => {
  const ids = new Set<number>();
  for (const job of livePipelineJobsById.value.values()) {
    if (job.data_entry_type_id != null) ids.add(job.data_entry_type_id);
  }
  return ids;
});

const pipelineAppliesToCard = computed<boolean>(() => {
  const p = props.pipelineProgress;
  if (!p) return false;
  if (props.targetType === undefined) return false;
  const allowedKinds = TARGET_TO_KINDS[props.targetType];
  if (!allowedKinds || !p.kind) return false;
  if (!allowedKinds.includes(p.kind)) return false;
  // Det-scoping: when this card maps to a specific submodule det and
  // the pipeline declares which dets it touches, only show the phase
  // if this card's det is among them.  A module-level card (no det)
  // or an empty det set (module-wide ingest before recalc fan-out, or
  // older payloads without the field) falls through to "show" —
  // preserving prior behavior.
  const det = props.row?.dataEntryTypeId;
  const detSet = pipelineDataEntryTypeIds.value;
  if (det != null && detSet.size > 0) {
    return detSet.has(det);
  }
  return true;
});

const pipelinePhaseLabelKey = computed<string | null>(() => {
  if (!pipelineAppliesToCard.value) return null;
  const p = props.pipelineProgress;
  if (!p || p.done || p.has_error) return null;
  return PIPELINE_PHASE_LABEL_KEYS[p.phase_label] ?? null;
});

// Pipeline-in-progress flag for the "validated" ✓ indicator below.
// Same card-scoping rule: a factor upload's running pipeline shouldn't
// turn the data card's ✓ amber.  Gated on ``pipelineAppliesToCard``.
const pipelineStillRunning = computed<boolean>(() => {
  if (!pipelineAppliesToCard.value) return false;
  const p = props.pipelineProgress;
  return !!(p && !p.done);
});

function handleUpload() {
  if (props.row && props.targetType !== undefined) {
    emit('upload', props.row, props.targetType);
  }
}

function handleDownload() {
  if (props.row && props.targetType !== undefined) {
    emit('download', props.row, props.targetType);
  }
}

// TODO: remove emit('recalculate', props.row); related code in the frontend and backend

function handleComputeFactors() {
  if (props.row) {
    emit('compute-factors', props.row);
  }
}

function handleAbort() {
  emit('abort');
}
</script>

<template>
  <q-card flat class="q-pa-lg column" :style="cardStyle(buttonColor)">
    <!-- Title and description -->
    <div class="row items-center q-mb-xs">
      <div class="text-body2 text-weight-bold">
        {{ title }}
      </div>
      <q-space />
      <span v-if="showMandatoryIndicator" class="text-caption text-grey-5">
        <span class="text-negative">*</span> {{ $t('common_mandatory') }}
      </span>
    </div>

    <div class="text-caption text-secondary q-mb-md">
      {{ description }}
    </div>

    <div v-if="descriptionSubtext" class="q-mb-xs text-caption text-grey-7">
      {{ descriptionSubtext }}
    </div>

    <!-- Upload button row -->
    <div
      class="row justify-between items-center full-width"
      style="margin-top: auto"
    >
      <div class="row q-mr-xs items-center" style="gap: 0.5rem">
        <!-- <q-spinner-rings v-if="isLoading" color="grey" /> -->
        <q-btn
          :color="buttonColor"
          :icon="buttonIcon"
          size="sm"
          :label="buttonLabel"
          class="text-weight-medium"
          :disable="isDisabled || isLoading"
          @click="handleUpload"
        />

        <!-- Computed factor button -->
        <template v-if="hasComputedFactorButton">
          <q-spinner-rings v-if="computedFactorRunning" color="grey" />
          <q-btn
            v-else
            color="accent"
            outline
            :icon="matCalculate"
            size="sm"
            :label="$t('data_management_compute_factors')"
            class="text-weight-medium"
            :disable="isDisabled || isComputedFactorDisabled"
            @click="handleComputeFactors"
          />
        </template>
      </div>

      <!-- Download and file info -->
      <div
        v-if="lastJob?.meta"
        class="row items-center no-wrap"
        style="gap: 0.75rem"
      >
        <div class="column">
          <div class="row items-center text-body2 text-weight-medium">
            <!-- Green ✓ only when the FULL pipeline is done — while
                 emission_recalc / aggregation children are still
                 running, show an amber ⋯ so the config page tells the
                 same story as the pipeline-ops console.  Previously
                 the ✓ appeared the moment csv_ingest finished and
                 read as "all done" even though downstream was still
                 in flight. -->
            <span
              v-if="pipelineStillRunning"
              class="text-warning q-mr-xs"
              :title="$t('data_management_pipeline_running_tooltip')"
            >
              ⋯
            </span>
            <span v-else class="text-positive q-mr-xs">✓</span>
            {{ jobInfo.fileName }}
          </div>
          <div class="text-caption text-grey-7">
            <span v-if="jobInfo.rowsProcessed !== undefined">
              {{ jobInfo.rowsProcessed }}
              {{ $t('data_management_rows_imported') }}
            </span>
            <span v-if="jobInfo.timestamp">
              {{ jobInfo.rowsProcessed !== undefined ? '•' : '' }}
              {{ jobInfo.timestamp.toLocaleDateString() }}
            </span>
          </div>
        </div>
        <q-btn
          v-if="lastJob?.ingestion_method !== IngestionMethod.API"
          color="positive"
          :icon="outlinedDownload"
          size="sm"
          unelevated
          dense
          @click="handleDownload"
        >
          <q-tooltip>{{ $t('data_management_download_last_csv') }}</q-tooltip>
        </q-btn>
        <q-icon
          v-if="hasErrorOrWarn"
          :name="matInfo"
          size="sm"
          class="cursor-pointer"
        >
          <q-tooltip>
            <div class="text-left">
              {{ errorDetails.message }}:
              <span v-if="errorDetails.error" class="text-negative">
                {{ errorDetails.error }}
              </span>
              <hr />
              <div
                v-for="(value, key, index) in errorDetails.stats || []"
                :key="index"
              >
                {{ key }}: {{ value }}
              </div>
            </div>
          </q-tooltip>
        </q-icon>
      </div>
    </div>

    <!-- Issue #1219 + UX consolidation — ONE in-progress indicator
         covering both the live csv_ingest (``isJobStuck``) and the
         downstream recalc/aggregation phases (``pipelinePhaseLabelKey``).
         Previously each rendered its own spinner-and-text row; during
         phase 1 BOTH showed simultaneously ("Job in progress…" + "Step
         1/3 · Inserting data…"), giving three loading icons on a single
         card.  Now: one spinner, phase-label when available, plus the
         abort button for the WHOLE time the pipeline is in flight on
         this card — including phase 2 (emissions) and phase 3
         (aggregation), where the operator most wants to stop a long
         recalc.  Pre-abort-refactor this button was gated on
         ``isJobStuck`` alone (i.e. only while the PARENT was running)
         and disappeared once phase 1 finished, leaving no way to stop
         a misfired chain mid-fanout. -->
    <div
      v-if="isJobStuck || pipelinePhaseLabelKey"
      class="row items-center text-caption q-mt-xs text-grey-7"
      style="gap: 0.5rem"
      data-testid="pipeline-phase"
    >
      <q-spinner-rings color="grey" size="sm" />
      <span>{{
        pipelinePhaseLabelKey
          ? $t(pipelinePhaseLabelKey)
          : $t('data_management_job_in_progress')
      }}</span>
      <q-btn
        color="negative"
        outline
        :icon="matCancel"
        size="sm"
        :label="$t('data_management_cancel_job')"
        class="text-weight-medium q-ml-sm"
        @click="handleAbort"
      />
    </div>

    <!-- API ingestion status (success: small inline line; error: banner below) -->
    <div
      v-if="apiJob && !hasApiErrorOrWarn"
      class="row items-center text-caption q-mt-xs text-grey-7"
      data-testid="api-status-success"
    >
      <span class="text-positive q-mr-xs">✓</span>
      <span>{{ $t('data_management_api_ingestion') }}:</span>
      <span v-if="apiJobInfo.rowsProcessed !== undefined" class="q-ml-xs">
        {{ apiJobInfo.rowsProcessed }}
        {{ $t('data_management_rows_imported') }}
      </span>
      <span v-if="apiJobInfo.timestamp" class="q-ml-xs">
        • {{ apiJobInfo.timestamp.toLocaleDateString() }}
      </span>
    </div>

    <!-- Error/warning banner -->
    <div
      v-if="hasErrorOrWarn"
      class="q-mt-md q-pa-md bg-grey-2 rounded-borders"
    >
      <div class="text-body2 text-weight-bold q-mb-sm text-negative">
        {{ errorDetails.message }}
      </div>
      <div
        v-if="errorDetails.error && errorDetails.error !== errorDetails.message"
        class="text-body2 q-mb-md"
      >
        {{ errorDetails.error }}
      </div>
      <div
        v-for="(value, key, index) in errorDetails.stats || []"
        :key="index"
        class="text-caption text-grey-7"
      >
        {{ key }}: {{ value }}
      </div>
    </div>

    <!-- API ingestion error/warning banner (secondary, below the CSV one) -->
    <div
      v-if="hasApiErrorOrWarn"
      class="q-mt-sm q-pa-md bg-grey-2 rounded-borders"
      data-testid="api-status-error"
    >
      <div class="text-body2 text-weight-bold q-mb-sm text-negative">
        {{ $t('data_management_api_ingestion') }}:
        {{ apiErrorDetails.message }}
      </div>
      <div
        v-if="
          apiErrorDetails.error &&
          apiErrorDetails.error !== apiErrorDetails.message
        "
        class="text-body2"
      >
        {{ apiErrorDetails.error }}
      </div>
    </div>
  </q-card>
</template>
