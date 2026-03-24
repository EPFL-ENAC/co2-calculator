<script setup lang="ts">
import { ref, watch } from 'vue';
import { useFilesStore, type FileObject } from 'src/stores/files';
import { useBackofficeDataManagement } from 'src/stores/backofficeDataManagement';
import type {
  SyncJobResponse,
  JobUpdatePayload,
} from 'src/stores/backofficeDataManagement';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

const filesStore = useFilesStore();
const dataManagementStore = useBackofficeDataManagement();
const $q = useQuasar();
const { t: $t } = useI18n();

interface Props {
  modelValue: boolean;
  row: ImportRow;
  year: number;
  targetType: 'data_entries' | 'factors';
}

interface ImportRow {
  key: string;
  labelKey: string;
  moduleTypeId: number;
  dataEntryTypeId?: number;
  factorVariant?: 'plane' | 'train';
  hasFactors: boolean;
  hasApi: boolean;
  hasData: boolean;
  other?: string;
  hasOtherUpload?: boolean;
  isDisabled?: boolean;
  lastDataJob?: SyncJobResponse;
  lastJobId?: number;
  lastJobState?: number;
  lastJobResult?: number;
  lastJobMeta?: {
    rows_processed?: number;
    rows_skipped?: number;
    file_path?: string;
  };
}

const props = withDefaults(defineProps<Props>(), {});
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'completed', job: SyncJobResponse): void;
}>();

const showDialog = ref<boolean>(false);
const activeTab = ref<string>('upload');
const selectedFiles = ref<FileObject[]>([]);
const isUploading = ref<boolean>(false);
const isConnecting = ref<boolean>(false);
const isCopying = ref<boolean>(false);

// API form fields
const apiServerUrl = ref<string>('');
const apiClientId = ref<string>('');
const apiSecretId = ref<string>('');
const apiSecretValue = ref<string>('');
const apiConnectionTesting = ref<boolean>(false);
const apiConnectionResult = ref<'success' | 'error' | null>(null);

// Previous year jobs
const previousYearJobs = ref<SyncJobResponse[]>([]);
const selectedPreviousJob = ref<number | null>(null);

watch(
  () => props.modelValue,
  (newVal) => {
    showDialog.value = newVal;
    if (newVal) {
      resetDialog();
      loadPreviousYearJobs();
    }
  },
);

watch(showDialog, (newVal) => {
  emit('update:modelValue', newVal);
});

function resetDialog() {
  activeTab.value = 'upload';
  selectedFiles.value = [];
  isUploading.value = false;
  isConnecting.value = false;
  isCopying.value = false;
  apiServerUrl.value = '';
  apiClientId.value = '';
  apiSecretId.value = '';
  apiSecretValue.value = '';
  apiConnectionResult.value = null;
  selectedPreviousJob.value = null;
  previousYearJobs.value = [];
}

async function loadPreviousYearJobs() {
  const previousYear = props.year - 1;
  try {
    const jobs = await dataManagementStore.getPreviousYearSuccessfulJobs(
      previousYear,
      props.row.moduleTypeId,
      props.targetType,
    );
    previousYearJobs.value = jobs;
    if (jobs.length > 0) {
      selectedPreviousJob.value = jobs[0].job_id;
    }
  } catch (err) {
    console.error('Failed to load previous year jobs:', err);
    previousYearJobs.value = [];
  }
}

// CSV Upload
const uploadFiles = async () => {
  if (!selectedFiles.value || selectedFiles.value.length === 0) {
    $q.notify({
      color: 'negative',
      message: $t('csv_no_files_uploaded'),
      position: 'top',
      closeBtn: true,
    });
    return;
  }

  isUploading.value = true;
  try {
    const uploadedFiles = await filesStore.uploadTempFiles(selectedFiles.value);
    const filePaths = uploadedFiles.map((file) => file.path);
    await initiateSync('csv', filePaths[0]);
    showDialog.value = false;
  } catch (err) {
    console.error('Error uploading files:', err);
    $q.notify({
      color: 'negative',
      message: $t('csv_sync_failed'),
      position: 'top',
    });
  } finally {
    isUploading.value = false;
  }
};

// API Connection
const testApiConnection = async () => {
  apiConnectionTesting.value = true;
  apiConnectionResult.value = null;

  try {
    // For now, we'll just validate that fields are filled
    // In a real implementation, this would call the backend to test the connection
    if (
      !apiServerUrl.value ||
      !apiClientId.value ||
      !apiSecretId.value ||
      !apiSecretValue.value
    ) {
      throw new Error('All fields are required');
    }

    // Simulate connection test (replace with actual API call)
    await new Promise((resolve) => setTimeout(resolve, 1000));

    apiConnectionResult.value = 'success';
    $q.notify({
      color: 'positive',
      message: $t('data_management_connection_success'),
      position: 'top',
    });
  } catch {
    apiConnectionResult.value = 'error';
    $q.notify({
      color: 'negative',
      message: $t('data_management_connection_failed'),
      position: 'top',
    });
  } finally {
    apiConnectionTesting.value = false;
  }
};

const connectAndSync = async () => {
  // if (
  //   !apiServerUrl.value ||
  //   !apiClientId.value ||
  //   !apiSecretId.value ||
  //   !apiSecretValue.value
  // ) {
  //   $q.notify({
  //     color: 'negative',
  //     message: 'All fields are required',
  //     position: 'top',
  //   });
  //   return;
  // }

  isConnecting.value = true;
  try {
    await initiateSync('api', undefined, undefined);
    showDialog.value = false;
  } catch (err) {
    if (err instanceof Error) {
      console.error('Error connecting to API:', err.message);
    }
    $q.notify({
      color: 'negative',
      message: $t('data_management_connection_failed'),
      position: 'top',
    });
  } finally {
    isConnecting.value = false;
  }
};

// Copy from Previous Year
const copyFromPreviousYear = async () => {
  if (!selectedPreviousJob.value) {
    $q.notify({
      color: 'negative',
      message: $t('data_management_no_previous_jobs'),
      position: 'top',
    });
    return;
  }

  isCopying.value = true;
  try {
    await initiateSync('copy', undefined, selectedPreviousJob.value);
    showDialog.value = false;
  } catch (err) {
    if (err instanceof Error) {
      console.error('Error copying from previous year:', err.message);
    }
    $q.notify({
      color: 'negative',
      message: $t('data_management_copy_failed'),
      position: 'top',
    });
  } finally {
    isCopying.value = false;
  }
};

// Common sync initiation
async function initiateSync(
  providerType: 'csv' | 'api' | 'copy',
  filePath?: string,
  sourceJobId?: number,
) {
  const syncParams: Record<string, unknown> = {
    module_type_id: props.row.moduleTypeId,
    year: props.year,
    provider_type: providerType === 'copy' ? 'csv' : providerType,
    target_type: props.targetType,
  };

  if (props.row.dataEntryTypeId !== undefined) {
    syncParams.data_entry_type_id = props.row.dataEntryTypeId;
  }

  if (props.row.factorVariant !== undefined) {
    syncParams.config = {
      factor_variant: props.row.factorVariant,
    };
  }

  if (filePath) {
    syncParams.file_path = filePath;
  }

  if (sourceJobId && providerType === 'copy') {
    const existingConfig = syncParams.config as
      | Record<string, unknown>
      | undefined;
    syncParams.config = {
      ...(existingConfig || {}),
      source_job_id: sourceJobId,
    };
  }
  const jobId = await dataManagementStore.initiateSync({
    module_type_id: props.row.moduleTypeId,
    year: props.year,
    provider_type: providerType === 'copy' ? 'csv' : providerType,
    target_type: props.targetType,
    data_entry_type_id: props.row.dataEntryTypeId,
    config: syncParams.config as Record<string, unknown>,
    file_path: filePath,
  });

  // Subscribe to job updates
  dataManagementStore.subscribeToJobUpdates(
    jobId,
    (payload?: JobUpdatePayload) => {
      // Determine notification type based on result (SUCCESS, WARNING, ERROR)
      const result = payload?.result;
      const rowsProcessed = payload?.meta?.rows_processed as number | undefined;
      const rowsSkipped = payload?.meta?.rows_skipped as number | undefined;

      let color: string;
      let message: string;
      let caption: string;

      if (result === 1) {
        // WARNING: some rows skipped
        color = 'warning';
        message = $t('csv_sync_completed_with_warnings');
        caption = $t('csv_sync_warnings_caption', {
          processed: rowsProcessed || 0,
          skipped: rowsSkipped || 0,
        });
      } else if (result === 0) {
        // SUCCESS: all rows processed
        color = 'positive';
        message = $t('csv_sync_completed');
        caption = $t('csv_sync_success_caption', {
          processed: rowsProcessed || 0,
        });

        // Emit completed event to parent for refresh
        if (payload) {
          emit('completed', {
            job_id: payload.job_id,
            module_type_id: payload.module_type_id,
            year: payload.year ?? props.year,
            target_type: payload.target_type as 0 | 1,
            state: payload.state ?? 3,
            result: payload.result ?? 0,
            status_message: payload.status_message,
            meta: payload.meta,
          } as SyncJobResponse);
        }
      } else {
        // ERROR: nothing processed or failed
        color = 'negative';
        message = $t('csv_sync_failed');
        caption = payload?.status_message || '';
      }

      $q.notify({
        color,
        message,
        caption,
        position: 'top',
        timeout: 5000,
      });
      console.log('Sync completed:', payload);
    },
    (payload?: JobUpdatePayload) => {
      $q.notify({
        color: 'negative',
        message: $t('csv_sync_failed'),
        caption: payload?.status_message || $t('csv_sync_failed_caption'),
        position: 'top',
        timeout: 5000,
      });
      console.error('Sync failed:', payload);
    },
    () => {
      $q.notify({
        color: 'negative',
        message: $t('csv_sync_connection_lost'),
        caption: $t('csv_sync_connection_lost_caption'),
        position: 'top',
        timeout: 30000,
      });
    },
  );
}
</script>

<template>
  <q-dialog v-model="showDialog" class="modal modal--lg" persistent>
    <q-card class="column">
      <q-card-section class="flex justify-between items-center flex-shrink">
        <div class="text-h4 text-weight-medium">
          {{ $t('data_management_import_title', { type: targetType }) }}
        </div>
        <q-btn
          v-close-popup
          flat
          size="md"
          icon="o_close"
          color="grey-6"
          class="text-weight-medium"
        />
      </q-card-section>
      <q-separator />

      <!-- Tabs -->
      <q-tabs
        v-model="activeTab"
        :align="'justify'"
        class="text-grey"
        :shrink="true"
      >
        <q-tab
          name="upload"
          :label="$t('data_management_tab_upload_csv')"
          icon="file_upload"
        />
        <q-tab
          :disable="!row.hasApi"
          name="api"
          :label="$t('data_management_tab_connect_api')"
          icon="link"
        />
        <q-tab
          name="copy"
          :label="$t('data_management_tab_copy_previous')"
          icon="file_copy"
        />
      </q-tabs>
      <q-separator />

      <q-card-section>
        <q-tab-panels v-model="activeTab" animated>
          <!-- Upload CSV Tab -->
          <q-tab-panel name="upload" class="q-pa-none">
            <!-- <div class="text-h6 q-mb-md">
              {{ $t('data_management_tab_upload_csv') }}
            </div> -->
            <q-banner
              v-if="row.lastDataJob && row.lastDataJob.result !== 2"
              color="warning"
              class="q-mb-md"
              inline-action
            >
              <q-icon name="warning" size="sm" class="q-mr-sm" />
              {{ $t('data_management_last_upload_overwrite') }}
            </q-banner>
            <q-form class="q-gutter-md" @submit.prevent="uploadFiles">
              <q-file
                v-model="selectedFiles"
                dense
                outlined
                multiple
                :hint="$t('data_management_supported_file_types')"
                counter
                accept=".csv, text/csv"
                @keyup.enter="uploadFiles"
              />
              <q-btn
                :label="$t('data_management_upload')"
                size="sm"
                color="accent"
                type="submit"
                :disabled="
                  !selectedFiles || selectedFiles.length === 0 || isUploading
                "
              />
              <q-linear-progress
                v-if="isUploading"
                indeterminate
                color="accent"
              />
            </q-form>
          </q-tab-panel>

          <!-- Connect API Tab -->
          <q-tab-panel v-if="row.hasApi" name="api" class="q-pa-none">
            <!-- <div class="text-h6 q-mb-md">
              {{ $t('data_management_tab_connect_api') }}
            </div> -->
            <q-form class="q-gutter-md" @submit.prevent="connectAndSync">
              <q-input
                v-model="apiServerUrl"
                dense
                outlined
                :label="$t('data_management_api_server_url')"
                placeholder="https://api.example.com"
              />
              <q-input
                v-model="apiClientId"
                dense
                outlined
                :label="$t('data_management_api_client_id')"
                placeholder="client-id"
              />
              <q-input
                v-model="apiSecretId"
                dense
                outlined
                :label="$t('data_management_api_secret_id')"
                placeholder="secret-id"
              />
              <q-input
                v-model="apiSecretValue"
                dense
                outlined
                type="password"
                auto-complete="current-password"
                :label="$t('data_management_api_secret_value')"
                placeholder="secret-value"
              />

              <div class="row q-gutter-sm">
                <q-btn
                  :label="$t('data_management_api_test_connection')"
                  outline
                  color="primary"
                  size="sm"
                  :disable="apiConnectionTesting"
                  @click="testApiConnection"
                />
                <q-btn
                  :label="$t('data_management_api_connect_and_sync')"
                  color="accent"
                  type="submit"
                  size="sm"
                  :disable="isConnecting"
                />
              </div>

              <q-linear-progress
                v-if="apiConnectionTesting || isConnecting"
                indeterminate
                color="accent"
              />
            </q-form>
          </q-tab-panel>

          <!-- Copy from Previous Year Tab -->
          <q-tab-panel name="copy" class="q-pa-none">
            <!-- <div class="text-h6 q-mb-md">
              {{ $t('data_management_tab_copy_previous') }}
            </div> -->
            <div
              v-if="previousYearJobs.length === 0"
              class="text-grey-7 q-pa-md"
            >
              {{ $t('data_management_no_previous_jobs') }}
            </div>
            <div v-else class="q-gutter-md">
              <q-select
                v-model="selectedPreviousJob"
                :options="
                  previousYearJobs.map((job) => ({
                    value: job.job_id,
                    label: `${$t('data_management_copy_from_year', { year: job.year })} - ${job.status_message || ''}`,
                  }))
                "
                emit-value
                map-options
                dense
                outlined
                :label="$t('data_management_select_import')"
              />
              <q-btn
                :label="$t('data_management_copy_start')"
                color="accent"
                size="sm"
                :disable="!selectedPreviousJob || isCopying"
                @click="copyFromPreviousYear"
              />
              <q-linear-progress
                v-if="isCopying"
                indeterminate
                color="accent"
              />
            </div>
          </q-tab-panel>
        </q-tab-panels>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<style scoped>
:deep(.q-tabs__arrow) {
  display: none !important;
}
</style>
