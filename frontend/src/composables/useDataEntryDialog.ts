import { ref, computed, watch, type Ref } from 'vue';
import { useFilesStore, type FileObject } from 'src/stores/files';
import {
  useBackofficeDataManagement,
  TargetType,
  type SyncJobResponse,
  type JobUpdatePayload,
  type ImportRow,
} from 'src/stores/backofficeDataManagement';
import {
  useConnectorsStore,
  type ConnectorSpecRead,
} from 'src/stores/connectors';
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
  const connectorsStore = useConnectorsStore();
  const $q = useQuasar();
  const { t: $t } = useI18n();

  const showDialog = ref<boolean>(false);
  const selectedFiles = ref<FileObject[]>([]);
  const isUploading = ref<boolean>(false);
  const isConnecting = ref<boolean>(false);
  const isCopying = ref<boolean>(false);

  const connectorsList = ref<ConnectorSpecRead[]>([]);
  const selectedConnector = ref<string>('');
  const apiConnectorLuid = ref<string>('');
  // Connections are configured once per connector from the backoffice
  // "API Connectors" card, not per module — this only tracks whether one
  // already exists so a datasource save doesn't 404 against a connector
  // nobody has set up yet.
  const connectionConfigured = ref<boolean>(false);

  const previousYearJobs = ref<SyncJobResponse[]>([]);
  const selectedPreviousJob = ref<number | null>(null);

  const allApiFieldsFilled = computed(
    () =>
      options.row.value.hasApi &&
      !!selectedConnector.value &&
      connectionConfigured.value &&
      !!apiConnectorLuid.value,
  );

  const showOverwriteWarning = computed(() => {
    const lastJob =
      options.targetType.value === TargetType.DATA_ENTRIES.valueOf()
        ? options.row.value.lastDataJob
        : options.row.value.lastFactorJob;
    return !!lastJob && lastJob.result !== 2;
  });

  const showOverwriteWarningAPI = computed(() => {
    const lastJob = options.row.value?.hasApi
      ? options.row.value?.lastApiDataJob
      : null;
    return !!lastJob && lastJob?.result !== 2;
  });

  function resetDialog() {
    selectedFiles.value = [];
    isUploading.value = false;
    isConnecting.value = false;
    isCopying.value = false;
    connectorsList.value = [];
    selectedConnector.value = '';
    apiConnectorLuid.value = '';
    connectionConfigured.value = false;
    selectedPreviousJob.value = null;
    previousYearJobs.value = [];
  }

  /** Check whether the currently selected connector already has a saved
   * connection — configuring one happens in the "API Connectors" card,
   * not here. */
  async function loadConnectionForSelectedConnector() {
    if (!selectedConnector.value) return;
    try {
      const conn = await connectorsStore.getConnection(selectedConnector.value);
      connectionConfigured.value = !!conn;
    } catch {
      connectionConfigured.value = false;
    }
  }

  watch(selectedConnector, loadConnectionForSelectedConnector);

  /**
   * Load the connector registry and prefill the connection form. Only
   * relevant for the DATA_ENTRIES tab of API-enabled rows — mirrors the
   * template's `row.hasApi && targetType === DATA_ENTRIES` guard.
   */
  async function loadConnectorOptions() {
    if (
      !options.row.value.hasApi ||
      options.targetType.value !== TargetType.DATA_ENTRIES.valueOf()
    ) {
      return;
    }
    try {
      connectorsList.value = await connectorsStore.listConnectors();
      if (connectorsList.value.length > 0) {
        // Triggers loadConnectionForSelectedConnector() via the watcher above.
        selectedConnector.value = connectorsList.value[0].connector;
      }
    } catch {
      connectorsList.value = [];
    }
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
      await connectorsStore.saveDatasource(selectedConnector.value, {
        module_type_id: options.row.value.moduleTypeId,
        data_entry_type_id: options.row.value.dataEntryTypeId,
        connector_luid: apiConnectorLuid.value,
        label: $t(options.row.value.labelKey),
      });
      await initiateSync('api', undefined, undefined);
      showDialog.value = false;
    } catch (err: unknown) {
      // The `api` client's afterResponse hook already surfaced the
      // backend's 422/429 `detail` via its own notification (see
      // src/api/http.ts); this is the generic fallback shown alongside
      // it, mirroring uploadFiles()/copyFromPreviousYear() below.
      $q.notify({
        color: 'negative',
        message: $t('data_management_connection_failed'),
        caption: err instanceof Error ? err.message : undefined,
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
    const config: Record<string, unknown> = {};
    if (options.row.value.reductionObjectiveTypeId !== undefined) {
      config.reduction_objective_type_id =
        options.row.value.reductionObjectiveTypeId;
    }
    if (options.row.value.factorVariant !== undefined) {
      config.factor_variant = options.row.value.factorVariant;
    }
    if (sourceJobId && providerType === 'copy') {
      config.source_job_id = sourceJobId;
    }

    const syncPayload = {
      module_type_id: options.row.value.moduleTypeId,
      year: options.year.value,
      provider_type: providerType === 'copy' ? 'csv' : providerType,
      target_type: options.targetType.value,
      data_entry_type_id: options.row.value.dataEntryTypeId,
      config,
      file_path: filePath,
    };

    const jobId = await dataManagementStore.initiateSync(syncPayload);

    dataManagementStore.subscribeToJobUpdates(
      jobId,
      (payload?: JobUpdatePayload) => {
        const result = payload?.result;
        const rowsProcessed = payload?.meta?.rows_processed as
          number | undefined;
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
    connectorsList,
    selectedConnector,
    apiConnectorLuid,
    connectionConfigured,
    previousYearJobs,
    selectedPreviousJob,
    allApiFieldsFilled,
    showOverwriteWarning,
    showOverwriteWarningAPI,
    handleEnterKey,
    resetDialog,
    loadPreviousYearJobs,
    loadConnectorOptions,
    uploadFiles,
    connectAndSync,
    copyFromPreviousYear,
  };
}
