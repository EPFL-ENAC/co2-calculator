<script setup lang="ts">
import { computed, ref } from 'vue';
import { useUploadCard } from '@/composables/useUploadCard';
import { useCardPipelineScope } from '@/composables/useCardPipelineScope';
import {
  TargetType,
  IngestionResult,
  IngestionState,
  IngestionMethod,
} from '@/stores/backofficeDataManagement';
import type {
  ImportRow,
  SyncJobResponse,
} from '@/stores/backofficeDataManagement';
import type { RecalculationStatusEntry } from '@/stores/yearConfig';
import type { PipelineProgress } from '@/stores/pipelineStream';

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
  (e: 'upload', row: ImportRow, targetType: TargetType, file?: File): void;
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
const hasApiFatalError = computed(() => {
  const meta = props.apiJob?.meta as Record<string, unknown> | undefined;
  return props.apiJob?.result === IngestionResult.ERROR || Boolean(meta?.error);
});

// ``row_errors``/``row_errors_count`` are rendered separately via
// ``errorDetails.rowErrors`` (formatted "row N: reason" lines) — drop them
// here so the raw stats dump doesn't also render `row_errors:
// [object Object],[object Object]` right below it.
function statsWithoutRowErrors(
  stats?: Record<string, unknown>,
): Record<string, unknown> {
  if (!stats) return {};
  const { row_errors, row_errors_count, ...rest } = stats;
  void row_errors;
  void row_errors_count;
  return rest;
}

const { pipelinePhaseLabelKey, pipelineStillRunning, dataIngestionRunning } =
  useCardPipelineScope(props);

// Drag-and-drop: the whole card is the drop target; the dropped file
// opens the shared import dialog pre-selected (overwrite + recalc
// warnings still apply — a stray drop never uploads by itself).
const isDragOver = ref(false);

function onDragOver() {
  if (props.isDisabled) return;
  isDragOver.value = true;
}

function onDragLeave() {
  isDragOver.value = false;
}

function onDrop(event: DragEvent) {
  isDragOver.value = false;
  const file = event.dataTransfer?.files[0];
  if (props.isDisabled || !file) return;
  handleUpload(file);
}

function handleUpload(file?: File) {
  if (props.row && props.targetType !== undefined) {
    emit('upload', props.row, props.targetType, file);
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
  <q-card
    flat
    class="q-pa-lg column relative-position"
    :style="cardStyle(buttonColor)"
    :data-testid="`upload-card-${targetType}-${row?.moduleTypeId}-${row?.dataEntryTypeId}`"
    @dragenter.prevent="onDragOver"
    @dragover.prevent="onDragOver"
    @drop.prevent="onDrop"
  >
    <!-- Covers every child while a file hovers, so dragleave only
         fires when the cursor actually leaves the card. -->
    <div
      v-if="isDragOver"
      class="upload-card__drop absolute-full flex flex-center text-h5 text-grey-6"
      data-testid="upload-card-drop-overlay"
      @dragleave="onDragLeave"
    >
      {{ $t('data_management_drop_csv_here') }}
    </div>
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
          @click="handleUpload()"
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
              {{ jobInfo.rowsProcessed !== undefined ? '·' : '' }}
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
          data-testid="download-last-csv-btn"
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
              <div v-if="errorDetails.rowErrors.length">
                <div
                  v-for="(line, index) in errorDetails.rowErrors"
                  :key="index"
                >
                  {{ line }}
                </div>
              </div>
              <div
                v-for="(value, key, index) in statsWithoutRowErrors(
                  errorDetails.stats,
                )"
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
        icon="cancel"
        size="sm"
        :label="$t('data_management_cancel_job')"
        class="text-weight-medium q-ml-sm"
        @click="handleAbort"
      />
    </div>

    <!-- API ingestion status (success/warning: inline; details below) -->
    <div
      v-if="apiJob && !hasApiFatalError && !dataIngestionRunning"
      class="row items-center text-caption q-mt-xs text-grey-7"
      data-testid="api-status-success"
    >
      <span
        :class="hasApiErrorOrWarn ? 'text-warning' : 'text-positive'"
        class="q-mr-xs"
      >
        {{ hasApiErrorOrWarn ? '!' : '✓' }}
      </span>
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
        v-if="errorDetails.rowErrors.length"
        class="text-caption text-grey-7"
      >
        <div v-for="(line, index) in errorDetails.rowErrors" :key="index">
          {{ line }}
        </div>
      </div>
      <div
        v-for="(value, key, index) in statsWithoutRowErrors(errorDetails.stats)"
        :key="index"
        class="text-caption text-grey-7"
      >
        {{ key }}: {{ value }}
      </div>
    </div>

    <!-- API ingestion error/warning banner (secondary, below the CSV one) -->
    <div
      v-if="hasApiErrorOrWarn && !dataIngestionRunning"
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
      <q-expansion-item
        v-if="apiErrorDetails.missingSyncedUnitErrors"
        dense
        switch-toggle-side
        class="q-mt-xs text-caption text-grey-7"
        :label="
          $t('data_management_missing_synced_units', {
            rows: apiErrorDetails.missingSyncedUnitErrors.rowsSkipped,
          })
        "
        :caption="
          $t('data_management_distinct_unit_ids', {
            count: apiErrorDetails.missingSyncedUnitErrors.units.length,
          })
        "
        data-testid="api-error-group-missing-synced-unit"
      >
        <q-list dense class="q-pb-xs">
          <q-item
            v-for="unit in apiErrorDetails.missingSyncedUnitErrors.units"
            :key="unit.unitInstitutionalId"
            dense
          >
            <q-item-section>
              {{
                $t(
                  unit.rowCount === 1
                    ? 'data_management_unit_row_count'
                    : 'data_management_unit_rows_count',
                  {
                    unit: unit.unitInstitutionalId,
                    count: unit.rowCount,
                  },
                )
              }}
            </q-item-section>
          </q-item>
        </q-list>
      </q-expansion-item>
      <div
        v-if="apiErrorDetails.rowErrors.length"
        class="text-caption text-grey-7 q-mt-xs"
      >
        <div v-for="(line, index) in apiErrorDetails.rowErrors" :key="index">
          {{ line }}
        </div>
      </div>
    </div>
  </q-card>
</template>

<style scoped>
.upload-card__drop {
  z-index: 1;
  border: 2px dashed var(--q-accent);
  border-radius: inherit;
  background: rgb(255 255 255 / 85%);
}
</style>
