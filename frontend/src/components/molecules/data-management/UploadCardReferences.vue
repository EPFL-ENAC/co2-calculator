<script setup lang="ts">
import { ref } from 'vue';
import { useUploadCard } from 'src/composables/useUploadCard';
import { useI18n } from 'vue-i18n';
import {
  useBackofficeDataManagement,
  TargetType,
  IngestionState,
  IngestionResult,
  EntityType,
} from 'src/stores/backofficeDataManagement';
import type {
  ImportRow,
  SyncJobResponse,
  JobUpdatePayload,
  InitiateSyncParams,
} from 'src/stores/backofficeDataManagement';
import { Notify } from 'quasar';

interface Props {
  row: ImportRow;
  year: number;
  isDisabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  isDisabled: false,
});

const emit = defineEmits<{
  (e: 'upload', row: ImportRow, entityType: EntityType): void;
  (e: 'completed', job: SyncJobResponse): void;
  (e: 'progressing', job: SyncJobResponse): void;
}>();

const { t } = useI18n();
const backofficeDataManagement = useBackofficeDataManagement();
const { safeFileName } = useUploadCard();

const isLoading = ref(false);
const lastJob = ref<SyncJobResponse | undefined>(undefined);

const QUASAR_COLOR_MAP: Record<string, string> = {
  accent: 'var(--q-accent)',
  positive: 'var(--q-positive)',
  negative: 'var(--q-negative)',
  warning: 'var(--q-warning)',
  'grey-4': '#bdbdbd',
};

function cardStyle(color: string): string {
  if (color === 'positive') {
    const c = QUASAR_COLOR_MAP['positive'];
    return `border: 1px solid ${c}; background-color: color-mix(in srgb, ${c} 10%, transparent)`;
  }
  return 'border: 1px solid rgba(0,0,0,0.12)';
}

function buttonColor(): string {
  if (props.isDisabled || props.row.isDisabled) return 'grey-4';
  if (!lastJob.value) return 'accent';
  if (lastJob.value.result === IngestionResult.ERROR) return 'negative';
  if (lastJob.value.result === IngestionResult.WARNING) return 'warning';
  return 'positive';
}

function buttonLabel(): string {
  if (props.isDisabled || props.row.isDisabled) return '';
  return lastJob.value
    ? t('data_management_reupload_reference')
    : t('data_management_upload_reference');
}

function getJobInfo(): {
  fileName: string | undefined;
  rowsProcessed: number | undefined;
  timestamp: Date | undefined;
} {
  if (!lastJob.value?.meta) {
    return {
      fileName: undefined,
      rowsProcessed: undefined,
      timestamp: undefined,
    };
  }

  const fileName = safeFileName(lastJob.value.meta);
  const rowsProcessed = (lastJob.value.meta as Record<string, unknown>)
    ?.rows_processed as number | undefined;
  const timestampStr = (lastJob.value.meta as Record<string, unknown>)
    ?.timestamp as string | undefined;
  const timestamp = timestampStr ? new Date(timestampStr) : undefined;

  return { fileName, rowsProcessed, timestamp };
}

function hasErrorOrWarning(): boolean {
  if (!lastJob.value) return false;
  return (
    lastJob.value.result === IngestionResult.WARNING ||
    lastJob.value.result === IngestionResult.ERROR
  );
}

function getErrorDetails(): {
  message: string;
  error?: string;
  stats?: Record<string, unknown>;
} {
  if (!lastJob.value) return { message: '' };

  const meta = lastJob.value.meta as Record<string, unknown> | undefined;
  return {
    message: lastJob.value.status_message || '',
    error: meta?.error as string | undefined,
    stats: meta?.stats as Record<string, unknown> | undefined,
  };
}

function downloadLastCsv(): void {
  if (!lastJob.value?.meta) return;
  const filePath = (lastJob.value.meta as Record<string, unknown>)
    .processed_file_path as string;
  if (!filePath) return;
  const a = document.createElement('a');
  a.href = `/api/v1/files/${filePath}`;
  a.download = filePath.split('/').pop() || filePath;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

async function handleUpload() {
  if (props.isDisabled || props.row.isDisabled) return;

  isLoading.value = true;

  try {
    const syncPayload: InitiateSyncParams = {
      module_type_id: props.row.moduleTypeId,
      year: props.year,
      provider_type: 'csv' as const,
      target_type: TargetType.REFERENCE_DATA,
      data_entry_type_id: props.row.dataEntryTypeId,
      config: {
        entity_type: EntityType.MODULE_UNIT_SPECIFIC,
      },
    };

    const jobId = await backofficeDataManagement.initiateSync(syncPayload);

    backofficeDataManagement.subscribeToJobUpdates(
      jobId,
      (payload?: JobUpdatePayload) => {
        const result = payload?.result;
        const rowsProcessed = payload?.meta?.rows_processed as
          | number
          | undefined;

        let color: string;
        let message: string;
        let caption: string;

        if (result === IngestionResult.WARNING) {
          color = 'warning';
          message = t('csv_sync_completed_with_warnings');
          caption = t('csv_sync_warnings_caption', {
            processed: rowsProcessed || 0,
            skipped: (payload?.meta?.rows_skipped as number) || 0,
          });
        } else if (result === IngestionResult.SUCCESS) {
          color = 'positive';
          message = t('csv_sync_completed');
          caption = t('csv_sync_success_caption', {
            processed: rowsProcessed || 0,
          });
        } else {
          color = 'negative';
          message = t('csv_sync_failed');
          caption = payload?.status_message || '';
        }

        if (payload) {
          const response: SyncJobResponse = {
            job_id: payload.job_id,
            module_type_id: payload.module_type_id,
            year: payload.year ?? props.year,
            target_type: payload.target_type,
            state: payload.state ?? IngestionState.FINISHED,
            result: payload.result ?? IngestionResult.ERROR,
            status_message: payload.status_message,
            meta: payload.meta,
          };
          lastJob.value = response;
          emit('completed', response);
        }

        Notify.create({
          color,
          message,
          caption,
          position: 'top',
          timeout: 5000,
        });
      },
      (payload?: JobUpdatePayload) => {
        Notify.create({
          color: 'negative',
          message: t('csv_sync_failed'),
          caption: payload?.status_message || t('csv_sync_failed_caption'),
          position: 'top',
          timeout: 5000,
        });
      },
      () => {
        Notify.create({
          color: 'negative',
          message: t('csv_sync_connection_lost'),
          caption: t('csv_sync_connection_lost_caption'),
          position: 'top',
          timeout: 30000,
        });
      },
      (payload?: JobUpdatePayload) => {
        if (!payload) return;
        emit('progressing', {
          job_id: payload.job_id,
          module_type_id: payload.module_type_id,
          year: payload.year ?? props.year,
          target_type: payload.target_type,
          state: payload.state ?? IngestionState.FINISHED,
          result: payload.result ?? IngestionResult.ERROR,
          status_message: payload.status_message,
          meta: payload.meta,
        });
      },
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '';
    Notify.create({
      type: 'negative',
      message: t('csv_sync_failed'),
      caption: msg,
      position: 'top',
    });
  } finally {
    isLoading.value = false;
  }
}

function hasLastJob(): boolean {
  return lastJob.value?.meta !== undefined;
}

function isErrorOrWarning(): boolean {
  return hasErrorOrWarning();
}
</script>

<template>
  <q-card flat class="q-pa-lg" :style="cardStyle(buttonColor())">
    <div class="row items-center q-mb-xs">
      <div class="text-body2 text-weight-bold">
        {{ $t('data_management_references') }}
      </div>
      <q-space />
      <span class="text-caption text-grey-5">
        <span class="text-negative">*</span> {{ $t('common_mandatory') }}
      </span>
    </div>

    <div class="text-caption text-secondary q-mb-md">
      {{ $t('data_management_references_description') }}
    </div>

    <div v-if="row.other" class="q-mb-xs text-caption text-grey-7">
      {{ $t(row.other) }}
    </div>

    <div class="row justify-between items-center full-width">
      <div class="row items-center" style="gap: 0.5rem">
        <q-spinner-rings v-if="isLoading" color="grey" />
        <q-btn
          no-caps
          :color="buttonColor()"
          icon="file_upload"
          size="sm"
          :label="buttonLabel()"
          class="text-weight-medium"
          :disable="isDisabled || row.isDisabled || isLoading"
          @click="handleUpload"
        >
          <q-tooltip v-if="isDisabled || row.isDisabled">{{
            $t('data_management_tbd')
          }}</q-tooltip>
        </q-btn>
      </div>

      <div
        v-if="hasLastJob()"
        class="row items-center no-wrap"
        style="gap: 0.75rem"
      >
        <div class="column items-end">
          <div class="row items-center text-body2 text-weight-medium">
            <span class="text-positive q-mr-xs">✓</span>
            {{ getJobInfo().fileName }}
          </div>
          <div class="text-caption text-grey-7">
            {{ getJobInfo().rowsProcessed }}
            {{ $t('data_management_rows_imported') }}
            <span v-if="getJobInfo().timestamp">
              • {{ getJobInfo().timestamp.toLocaleDateString() }}
            </span>
          </div>
        </div>
        <q-btn
          color="positive"
          icon="o_download"
          size="sm"
          unelevated
          dense
          @click="downloadLastCsv"
        >
          <q-tooltip>{{ $t('data_management_download_last_csv') }}</q-tooltip>
        </q-btn>
        <q-icon
          v-if="isErrorOrWarning()"
          name="info"
          size="sm"
          class="cursor-pointer"
        >
          <q-tooltip>
            <div class="text-left">
              {{ getErrorDetails().message }}:
              <span v-if="getErrorDetails().error" class="text-negative">
                {{ getErrorDetails().error }}
              </span>
              <hr />
              <div
                v-for="(value, key, index) in getErrorDetails().stats || []"
                :key="index"
              >
                {{ key }}: {{ value }}
              </div>
            </div>
          </q-tooltip>
        </q-icon>
      </div>
    </div>

    <div
      v-if="isErrorOrWarning()"
      class="q-mt-md q-pa-md bg-grey-2 rounded-borders"
    >
      <div class="text-body2 text-weight-bold q-mb-sm text-negative">
        {{ getErrorDetails().message }}
      </div>
      <div
        v-if="
          getErrorDetails().error &&
          getErrorDetails().error !== getErrorDetails().message
        "
        class="text-body2 q-mb-md"
      >
        {{ getErrorDetails().error }}
      </div>
      <div
        v-for="(value, key, index) in getErrorDetails().stats || []"
        :key="index"
        class="text-caption text-grey-7"
      >
        {{ key }}: {{ value }}
      </div>
    </div>
  </q-card>
</template>
