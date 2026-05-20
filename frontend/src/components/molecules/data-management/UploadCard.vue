<script setup lang="ts">
import { computed } from 'vue';
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
import type { PipelineProgress } from 'src/stores/pipelineStream';

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
  (e: 'cancel', jobId: number): void;
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
const apiRowsInserted = computed<number | undefined>(() => {
  const meta = props.apiJob?.meta as Record<string, unknown> | undefined;
  const inserted = meta?.inserted;
  return typeof inserted === 'number' ? inserted : undefined;
});

// Issue #1219 — live recalc-pipeline phase for this card. The pipeline
// is module-scoped, so every card in the module reflects the same
// phase while it runs (Data → Emissions → Aggregation). Hidden once
// the pipeline is done or errored (the error surfaces via lastJob).
const PIPELINE_PHASE_LABEL_KEYS: Record<string, string> = {
  data: 'data_management_pipeline_phase_data',
  emissions: 'data_management_pipeline_phase_emissions',
  aggregation: 'data_management_pipeline_phase_aggregation',
};

const pipelinePhaseLabelKey = computed<string | null>(() => {
  const p = props.pipelineProgress;
  if (!p || p.done || p.has_error) return null;
  return PIPELINE_PHASE_LABEL_KEYS[p.phase_label] ?? null;
});

// Pipeline-in-progress flag for the "validated" ✓ indicator below.
// The green ✓ next to the filename used to appear as soon as the
// upload job finished — even when emission_recalc / aggregation
// children were still running.  Operators read that as "all done"
// and were surprised to see RUNNING tasks on the pipeline-ops page.
// Now the ✓ stays amber (⋯) until the WHOLE pipeline finishes,
// matching what the pipeline-ops console shows.
const pipelineStillRunning = computed<boolean>(() => {
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

function handleCancel() {
  if (props.lastJob?.job_id) {
    emit('cancel', props.lastJob.job_id);
  }
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
        <q-spinner-rings v-if="isLoading" color="grey" />
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
            icon="calculate"
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
          icon="o_download"
          size="sm"
          unelevated
          dense
          @click="handleDownload"
        >
          <q-tooltip>{{ $t('data_management_download_last_csv') }}</q-tooltip>
        </q-btn>
        <q-icon
          v-if="hasErrorOrWarn"
          name="info"
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

      <!-- Stuck job: cancel button -->
      <div
        v-if="isJobStuck"
        class="row items-center no-wrap"
        style="gap: 0.5rem"
      >
        <q-spinner-rings color="grey" size="sm" />
        <span class="text-caption text-grey-7">{{
          $t('data_management_job_in_progress')
        }}</span>
        <q-btn
          color="negative"
          outline
          icon="cancel"
          size="sm"
          :label="$t('data_management_cancel_job')"
          class="text-weight-medium"
          @click="handleCancel"
        />
      </div>
    </div>

    <!-- Issue #1219 — live recalc-pipeline phase (module-scoped) -->
    <div
      v-if="pipelinePhaseLabelKey"
      class="row items-center text-caption q-mt-xs text-grey-7"
      data-testid="pipeline-phase"
    >
      <q-spinner-rings color="grey" size="sm" class="q-mr-xs" />
      <span>{{ $t(pipelinePhaseLabelKey) }}</span>
    </div>

    <!-- API ingestion status (success: small inline line; error: banner below) -->
    <div
      v-if="apiJob && !hasApiErrorOrWarn"
      class="row items-center text-caption q-mt-xs text-grey-7"
      data-testid="api-status-success"
    >
      <span class="text-positive q-mr-xs">✓</span>
      <span>{{ $t('data_management_api_ingestion') }}:</span>
      <span v-if="apiRowsInserted !== undefined" class="q-ml-xs">
        {{ apiRowsInserted }}
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
