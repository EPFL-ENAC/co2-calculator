<script setup lang="ts">
import { computed } from 'vue';
import { useUploadCard } from 'src/composables/useUploadCard';
import {
  TargetType,
  IngestionState,
} from 'src/stores/backofficeDataManagement';
import type {
  ImportRow,
  SyncJobResponse,
} from 'src/stores/backofficeDataManagement';
import type { RecalculationStatusEntry } from 'src/stores/yearConfig';

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
  targetType?: TargetType;
  hasRecalcButton?: boolean;
  recalcStatus?: RecalculationStatusEntry;
  recalcRunning?: boolean;
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
  targetType: undefined,
  hasRecalcButton: false,
  recalcStatus: undefined,
  recalcRunning: false,
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

function handleRecalculate() {
  if (props.row) {
    emit('recalculate', props.row);
  }
}

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

        <!-- Recalculation button -->
        <template v-if="hasRecalcButton">
          <q-spinner-rings v-if="recalcRunning" color="grey" />
          <template v-else>
            <q-btn
              color="accent"
              outline
              icon="refresh"
              :icon-right="
                recalcStatus?.needs_recalculation ? 'warning' : undefined
              "
              size="sm"
              :label="$t('data_management_recalculate_emissions')"
              :title="
                recalcStatus?.needs_recalculation
                  ? $t('data_management_recalculation_needed')
                  : ''
              "
              class="text-weight-medium"
              :disable="isDisabled"
              @click="handleRecalculate"
            />
          </template>
        </template>

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
            <span class="text-positive q-mr-xs">✓</span>
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
  </q-card>
</template>
