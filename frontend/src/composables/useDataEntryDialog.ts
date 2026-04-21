import { ref, computed, type Ref } from 'vue';
import { useFilesStore, type FileObject } from 'src/stores/files';
import {
  useBackofficeDataManagement,
  TargetType,
  type SyncJobResponse,
  type JobUpdatePayload,
  type ImportRow,
} from 'src/stores/backofficeDataManagement';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

interface UseDataEntryDialogOptions {
  row: Ref<ImportRow>;
  year: Ref<number>;
  targetType: Ref<TargetType>;
  onComplete: (job: SyncJobResponse) => void;
  onProgressing: (job: SyncJobResponse) => void;
}

export function useDataEntryDialog(options: UseDataEntryDialogOptions) {
  const filesStore = useFilesStore();
  const dataManagementStore = useBackofficeDataManagement();
  const $q = useQuasar();
  const { t: $t } = useI18n();

  const showDialog = ref<boolean>(false);
  const selectedFiles = ref<FileObject[]>([]);
  const isUploading = ref<boolean>(false);
  const isConnecting = ref<boolean>(false);
  const isCopying = ref<boolean>(false);

  const apiServerUrl = ref<string>('');
  const apiClientId = ref<string>('');
  const apiSecretId = ref<string>('');
  const apiSecretValue = ref<string>('');

  const previousYearJobs = ref<SyncJobResponse[]>([]);
  const selectedPreviousJob = ref<number | null>(null);

  const allApiFieldsFilled = computed(
    () =>
      options.row.value.hasApi &&
      !!apiServerUrl.value &&
      !!apiClientId.value &&
      !!apiSecretId.value &&
      !!apiSecretValue.value,
  );

  const showOverwriteWarning = computed(() => {
    const lastJob =
      options.targetType.value === TargetType.DATA_ENTRIES.valueOf()
        ? options.row.value.lastDataJob
        : options.row.value.lastFactorJob;
    return !!lastJob && lastJob.result !== 2;
  });

  const showOverwriteWarningAPI = computed(() => {
    const lastJob = options.row.value?.hasApi ? options.row.value?.lastApiDataJob : null;
    return !!lastJob && lastJob?.result !== 2;
  });

  function resetDialog() {
    selectedFiles.value = [];
    isUploading.value = false;
    isConnecting.value = false;
    isCopying.value = false;
    apiServerUrl.value = '';
    apiClientId.value = '';
    apiSecretId.value = '';
    apiSecretValue.value = '';
    selectedPreviousJob.value = null;
    previousYearJobs.value = [];
  }

  async function loadPreviousYearJobs() {
    const previousYear = options.year.value - 1;
    try {
      const jobs = await dataManagementStore.getPreviousYearSuccessfulJobs(
        previousYear,
        options.row.value.moduleTypeId,
        options.targetType.value,
      );
      previousYearJobs.value = jobs;
      if (jobs.length > 0) {
        selectedPreviousJob.value = jobs[0].job_id;
      }
    } catch {
      previousYearJobs.value = [];
    }
  }

  function handleEnterKey() {
    if (isUploading.value || isConnecting.value || isCopying.value) return;
    if (selectedFiles.value && selectedFiles.value.length > 0) {
      uploadFiles();
    } else if (allApiFieldsFilled.value) {
      connectAndSync();
    }
  }

  async function uploadFiles() {
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
      const uploadedFiles = await filesStore.uploadTempFiles(
        selectedFiles.value,
      );
      const filePaths = uploadedFiles.map((file) => file.path);
      await initiateSync('csv', filePaths[0]);
      showDialog.value = false;
    } catch {
      $q.notify({
        color: 'negative',
        message: $t('csv_sync_failed'),
        position: 'top',
      });
    } finally {
      isUploading.value = false;
    }
  }

  async function connectAndSync() {
    isConnecting.value = true;
    try {
      await initiateSync('api', undefined, undefined);
      showDialog.value = false;
    } catch {
      $q.notify({
        color: 'negative',
        message: $t('data_management_connection_failed'),
        position: 'top',
      });
    } finally {
      isConnecting.value = false;
    }
  }

  async function copyFromPreviousYear() {
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
    } catch {
      $q.notify({
        color: 'negative',
        message: $t('data_management_copy_failed'),
        position: 'top',
      });
    } finally {
      isCopying.value = false;
    }
  }

  async function initiateSync(
    providerType: 'csv' | 'api' | 'copy',
    filePath?: string,
    sourceJobId?: number,
  ) {
    const syncParams: Record<string, unknown> = {
      module_type_id: options.row.value.moduleTypeId,
      year: options.year.value,
      provider_type: providerType === 'copy' ? 'csv' : providerType,
      target_type: options.targetType.value,
      config: {},
    };

    if (options.row.value.dataEntryTypeId !== undefined) {
      syncParams.data_entry_type_id = options.row.value.dataEntryTypeId;
    }

    if (options.row.value.reductionObjectiveTypeId !== undefined) {
      const existingConfig = syncParams.config as
        | Record<string, unknown>
        | undefined;
      syncParams.config = {
        ...existingConfig,
        reduction_objective_type_id: options.row.value.reductionObjectiveTypeId,
      };
    }

    if (options.row.value.factorVariant !== undefined) {
      const existingConfig = syncParams.config as
        | Record<string, unknown>
        | undefined;
      syncParams.config = {
        ...existingConfig,
        factor_variant: options.row.value.factorVariant,
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

    const syncPayload = {
      module_type_id: options.row.value.moduleTypeId,
      year: options.year.value,
      provider_type: providerType === 'copy' ? 'csv' : providerType,
      target_type: options.targetType.value,
      data_entry_type_id: options.row.value.dataEntryTypeId,
      config: syncParams.config as Record<string, unknown>,
      file_path: filePath,
    };

    const jobId = await dataManagementStore.initiateSync(syncPayload);

    dataManagementStore.subscribeToJobUpdates(
      jobId,
      (payload?: JobUpdatePayload) => {
        const result = payload?.result;
        const rowsProcessed = payload?.meta?.rows_processed as
          | number
          | undefined;
        const rowsSkipped = payload?.meta?.rows_skipped as number | undefined;

        let color: string;
        let message: string;
        let caption: string;

        if (result === 1) {
          color = 'warning';
          message = $t('csv_sync_completed_with_warnings');
          caption = $t('csv_sync_warnings_caption', {
            processed: rowsProcessed || 0,
            skipped: rowsSkipped || 0,
          });
        } else if (result === 0) {
          color = 'positive';
          message = $t('csv_sync_completed');
          caption = $t('csv_sync_success_caption', {
            processed: rowsProcessed || 0,
          });
        } else {
          color = 'negative';
          message = $t('csv_sync_failed');
          caption = payload?.status_message || '';
        }

        if (payload) {
          options.onComplete({
            job_id: payload.job_id,
            module_type_id: payload.module_type_id,
            year: payload.year ?? options.year.value,
            target_type: payload.target_type,
            state: payload.state ?? 3,
            result: payload.result ?? 0,
            status_message: payload.status_message,
            meta: payload.meta,
          } as SyncJobResponse);
        }

        $q.notify({
          color,
          message,
          caption,
          position: 'top',
          timeout: 5000,
        });
      },
      (payload?: JobUpdatePayload) => {
        $q.notify({
          color: 'negative',
          message: $t('csv_sync_failed'),
          caption: payload?.status_message || $t('csv_sync_failed_caption'),
          position: 'top',
          timeout: 5000,
        });
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
      (payload?: JobUpdatePayload) => {
        if (!payload) return;
        options.onProgressing({
          job_id: payload.job_id,
          module_type_id: payload.module_type_id,
          year: payload.year ?? options.year.value,
          target_type: payload.target_type,
          state: payload.state ?? 3,
          result: payload.result ?? 0,
          status_message: payload.status_message,
          meta: payload.meta,
        } as SyncJobResponse);
      },
    );
  }

  return {
    showDialog,
    selectedFiles,
    isUploading,
    isConnecting,
    isCopying,
    apiServerUrl,
    apiClientId,
    apiSecretId,
    apiSecretValue,
    previousYearJobs,
    selectedPreviousJob,
    allApiFieldsFilled,
    showOverwriteWarning,
    showOverwriteWarningAPI,
    handleEnterKey,
    resetDialog,
    loadPreviousYearJobs,
    uploadFiles,
    connectAndSync,
    copyFromPreviousYear,
  };
}
