import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from 'src/api/http';
import { Module } from 'src/constant/modules';
import { getModuleTypeId } from 'src/constant/moduleStates';

export interface DataIngestionJob {
  job_id: number;
  module_type_id: number;
  year: number;
  provider_type: string;
  target_type: number;
  ingestion_method: number; // 0: api, 1: csv, 2: manual
  state?: number; // New: 0: NOT_STARTED, 1: QUEUED, 2: RUNNING, 3: FINISHED
  result?: number; // New: 0: SUCCESS, 1: WARNING, 2: ERROR (only valid when state is FINISHED)
  status_message?: string;
  meta?: Record<string, unknown>;
}

export interface ImportRow {
  key: string;
  labelKey: string; // label key of module_type // e.g 'headcount'
  labelDataEntryKey?: string;
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
  lastApiDataJob?: SyncJobResponse;
  lastFactorJob?: SyncJobResponse;
}

export interface JobRowError {
  row: number;
  reason: string;
}

export interface JobUpdatePayload {
  job_id: number;
  module_type_id: number;
  target_type: number;
  year: number | null;
  status: string | number;
  state?: number;
  result?: number;
  status_message: string;
  meta?: {
    row_errors?: JobRowError[];
    row_errors_count?: number;
    rows_processed?: number;
    rows_skipped?: number;
    rows_with_factors?: number;
    rows_without_factors?: number;
  };
}

export interface SyncJobStatus {
  module_type_id: number;
  year: number;
  state?: number; // New state
  result?: number; // New result
  provider_type: string;
}

export interface SyncJobResponse {
  job_id: number;
  module_type_id?: number;
  year?: number;
  ingestion_method?: IngestionMethod;
  target_type?: TargetType;
  state?: IngestionState;
  status_message?: string;
  meta?: Record<string, unknown>;
  result?: IngestionResult;
}

export enum IngestionMethod {
  API = 0,
  CSV = 1,
  MANUAL = 2,
}

export enum TargetType {
  DATA_ENTRIES = 0,
  FACTORS = 1,
}

export enum EntityType {
  MODULE_PER_YEAR = 2,
  MODULE_UNIT_SPECIFIC = 3,
}

export enum FactorType {
  EMISSION_FACTOR = 0,
  MODULE_FACTOR = 1,
}

export enum IngestionState {
  NOT_STARTED = 0,
  QUEUED = 1,
  RUNNING = 2,
  FINISHED = 3,
}

export enum IngestionResult {
  SUCCESS = 0,
  WARNING = 1,
  ERROR = 2,
}

export type InitiateSyncParams = {
  module_type_id: number;
  year?: number;
  provider_type: 'csv' | 'api';
  target_type?: TargetType;
  filters?: Record<string, unknown>;
  config?: Record<string, unknown>;
  file_path?: string;
  data_entry_type_id?: number;
  carbon_report_module_id?: number;
};

export const useBackofficeDataManagement = defineStore(
  'backofficeDataManagement',
  () => {
    // State
    const loading = ref(false);
    const error = ref<string | null>(null);
    const syncJobs = ref<Record<string, DataIngestionJob[]>>({}); // Initialize as empty object
    const currentYear = ref<number | null>(null);
    let sseConnection: EventSource | null = null;

    // Computed properties
    const syncJobStatuses = computed<SyncJobStatus[]>(() => {
      if (!currentYear.value) return [];

      const jobs = syncJobs.value[currentYear.value] || [];
      return jobs.map((job) => ({
        module_type_id: job.module_type_id,
        year: job.year,
        state: job.state,
        result: job.result,
        provider_type: job.provider_type,
      }));
    });

    // In the store, alongside your other computed properties
    const getLatestJobsByYear = computed(() => (year: number) => {
      return syncJobs.value[year] ?? [];
    });

    const getSyncStatusByModule = (
      moduleType: Module,
      year: number,
    ): number => {
      const moduleTypeId = getModuleTypeId(moduleType);
      const jobs = syncJobs.value[year] || [];
      const job = jobs.find((j) => j.module_type_id === moduleTypeId);
      return job ? (job.state ?? 0) : 0; // Default to NOT_STARTED (0) if no job found
    };

    /**
     * Get the new state value for a job by module type.
     * Returns the state enum value or 0 (NOT_STARTED) if no job found.
     */
    const getSyncStateByModule = (moduleType: Module, year: number): number => {
      const moduleTypeId = getModuleTypeId(moduleType);
      const jobs = syncJobs.value[year] || [];
      const job = jobs.find((j) => j.module_type_id === moduleTypeId);
      return job?.state ?? 0; // Default to NOT_STARTED (0) if no job found
    };

    /**
     * Get the result value for a job by module type.
     * Returns the result enum value or undefined if job not finished.
     */
    const getSyncResultByModule = (
      moduleType: Module,
      year: number,
    ): number | undefined => {
      const moduleTypeId = getModuleTypeId(moduleType);
      const jobs = syncJobs.value[year] || [];
      const job = jobs.find((j) => j.module_type_id === moduleTypeId);
      return job?.result;
    };

    /**
     * Check if a job is finished (state = FINISHED).
     */
    const isJobFinished = (moduleType: Module, year: number): boolean => {
      const moduleTypeId = getModuleTypeId(moduleType);
      const jobs = syncJobs.value[year] || [];
      const job = jobs.find((j) => j.module_type_id === moduleTypeId);
      return job?.state === IngestionState.FINISHED; // FINISHED
    };

    /**
     * Check if a job has succeeded (state = FINISHED && result = SUCCESS).
     */
    const hasJobSucceeded = (moduleType: Module, year: number): boolean => {
      const moduleTypeId = getModuleTypeId(moduleType);
      const jobs = syncJobs.value[year] || [];
      const job = jobs.find((j) => j.module_type_id === moduleTypeId);
      return (
        job?.state === IngestionState.FINISHED &&
        job?.result === IngestionResult.SUCCESS
      ); // FINISHED && SUCCESS
    };

    /**
     * Calculate the success rate of a job based on meta stats.
     * Returns percentage (0-100) or null if stats not available.
     *
     * Logic:
     * - 100% if rows_skipped === 0
     * - 0% if rows_processed === 0
     * - Otherwise: (rows_processed / (rows_processed + rows_skipped)) * 100
     */
    const getSuccessRate = (job: DataIngestionJob): number | null => {
      if (!job.meta) return null;

      const meta = job.meta as Record<string, unknown>;
      const stats = (meta as { stats?: Record<string, unknown> }).stats || meta;

      const rowsProcessed = (stats.rows_processed as number) || 0;
      const rowsSkipped = (stats.rows_skipped as number) || 0;

      if (rowsProcessed === 0) return 0;
      if (rowsSkipped === 0) return 100;

      const totalRows = rowsProcessed + rowsSkipped;
      return Math.round((rowsProcessed / totalRows) * 100);
    };

    /**
     * Get human-readable result label based on state and result.
     */
    const getResultLabel = (state?: number, result?: number): string => {
      if (state !== IngestionState.FINISHED) return 'In Progress';

      switch (result) {
        case IngestionResult.SUCCESS:
          return 'Success';
        case IngestionResult.WARNING:
          return 'Warning';
        case IngestionResult.ERROR:
          return 'Error';
        default:
          return 'Unknown';
      }
    };

    // Methods
    async function fetchSyncJobsByYear(
      year: number,
    ): Promise<DataIngestionJob[]> {
      if (loading.value) return [];

      loading.value = true;
      error.value = null;
      currentYear.value = year;

      try {
        const response = (await api
          .get(`sync/jobs/year/${year}`)
          .json()) as DataIngestionJob[];
        syncJobs.value[year] = response;
        return response;
      } catch (err: unknown) {
        if (err instanceof Error) {
          error.value = err.message ?? 'Failed to fetch sync jobs';
        } else {
          error.value = 'Failed to fetch sync jobs';
        }
        return [];
      } finally {
        loading.value = false;
      }
    }

    async function fetchLatestSyncJobsByYear(
      year: number,
    ): Promise<DataIngestionJob[]> {
      loading.value = true;
      error.value = null;
      currentYear.value = year;

      try {
        const response = (await api
          .get(`sync/jobs/year/${year}/latest`)
          .json()) as DataIngestionJob[];
        syncJobs.value[year] = response;
        return response;
      } catch (err: unknown) {
        if (err instanceof Error) {
          error.value = err.message ?? 'Failed to fetch latest sync jobs';
        } else {
          error.value = 'Failed to fetch latest sync jobs';
        }
        return [];
      } finally {
        loading.value = false;
      }
    }

    /*
  # example of payload:
# {
#   "provider_type": "tableau_api", | should be more like csv | api
#   "year": 2023,
#   "filters": {"date_from": "2023-01-01", "date_to": "2023-12-31"},
#   "config": {"site_id": "mysite", "project_id": "myproject"}
# }

target_type
provider_type
  */

    async function initiateSync({
      module_type_id,
      year,
      provider_type,
      target_type = TargetType.DATA_ENTRIES.valueOf(),
      filters,
      config,
      file_path,
      data_entry_type_id,
      carbon_report_module_id,
    }: InitiateSyncParams): Promise<number> {
      if (loading.value) throw new Error('Another operation is in progress');

      loading.value = true;
      error.value = null;

      try {
        const mergedConfig: Record<string, unknown> = { ...(config || {}) };
        if (data_entry_type_id !== undefined && data_entry_type_id !== null) {
          mergedConfig.data_entry_type_id = data_entry_type_id;
        }
        if (
          carbon_report_module_id !== undefined &&
          carbon_report_module_id !== null
        ) {
          mergedConfig.carbon_report_module_id = carbon_report_module_id;
        }

        // Prepare request body
        const requestBody: Record<string, unknown> = {
          ingestion_method:
            provider_type === 'api' ? IngestionMethod.API : IngestionMethod.CSV,
          target_type: target_type, // Use TargetType enum value
          year,
          filters: filters || {},
          config: mergedConfig,
        };

        // Add file_path if provided (for CSV uploads)
        if (file_path) {
          requestBody.file_path = file_path;
        }

        const response = (await api
          .post(`sync/data-entries/${module_type_id}`, {
            json: requestBody,
          })
          .json()) as { job_id: number };

        // Update local state with new job
        if (year !== undefined) {
          if (!syncJobs.value[year]) {
            syncJobs.value[year] = [];
          }
          syncJobs.value[year].push({
            job_id: response.job_id,
            module_type_id,
            year,
            provider_type,
            ingestion_method:
              provider_type === 'api'
                ? IngestionMethod.API
                : IngestionMethod.CSV,
            target_type,
            state: IngestionState.NOT_STARTED,
            status_message: 'Sync initiated',
            meta: {},
          });
        }

        return response.job_id;
      } catch (err: unknown) {
        if (err instanceof Error) {
          error.value = err.message ?? 'Failed to initiate sync';
        } else {
          error.value = 'Failed to initiate sync';
        }
        throw err;
      } finally {
        loading.value = false;
      }
    }

    /**
     * Subscribe to SSE stream for real-time job status updates.
     * Maps updates to the appropriate module/target rows via job_id,
     * module_type_id, and year.
     * payload will look like: {
          "job_id": 94,
          "module_type_id": 4,
          "target_type": 0,
          "year": null,
          "status": 0,
          "status_message": "Job created"
      }
     */
    function subscribeToJobUpdates(
      jobId?: number,
      onCompleted?: (payload?: JobUpdatePayload) => void,
      onFail?: (payload?: JobUpdatePayload) => void,
      onError?: () => void,
      onMessage?: (payload?: JobUpdatePayload) => void,
    ): void {
      if (!jobId) {
        return;
      }

      if (sseConnection) {
        sseConnection.close();
        sseConnection = null;
      }

      try {
        sseConnection = new EventSource(`/api/v1/sync/jobs/${jobId}/stream`);

        sseConnection.onmessage = (event: MessageEvent) => {
          try {
            const update: JobUpdatePayload = JSON.parse(event.data);

            // New state/result values (may be undefined for older data)
            const state = update.state;
            const result = update.result;

            const job_id = update.job_id;
            const year = update.year;

            // Find and update the job in the store
            if (year !== null && syncJobs.value[year]) {
              const jobIndex = syncJobs.value[year].findIndex(
                (j: DataIngestionJob) => j.job_id === job_id,
              );
              if (jobIndex !== -1) {
                syncJobs.value[year].splice(jobIndex, 1, {
                  ...syncJobs.value[year][jobIndex],
                  state,
                  result,
                  status_message: update.status_message || '',
                });
              }
            }

            // Use new state/result for completion detection if available
            // Fall back to legacy status for backward compatibility
            const isFinished = state === IngestionState.FINISHED;
            const isSuccess =
              state === IngestionState.FINISHED &&
              result === IngestionResult.SUCCESS;
            const isFailure =
              state === IngestionState.FINISHED &&
              result === IngestionResult.ERROR;

            if (isSuccess) {
              onCompleted?.(update);
            }

            if (isFailure) {
              onFail?.(update);
            }
            if (isFinished) {
              unsubscribeFromJobUpdates();
            }
            onMessage?.(update);
          } catch (err) {
            console.error('Error parsing SSE message:', err);
          }
        };

        sseConnection.onerror = () => {
          unsubscribeFromJobUpdates();
          onError?.();
        };
      } catch (err) {
        console.error('Failed to establish SSE connection:', err);
      }
    }

    /**
     * Unsubscribe from SSE stream and close the connection.
     */
    function unsubscribeFromJobUpdates(): void {
      if (sseConnection) {
        sseConnection.close();
        sseConnection = null;
      }
    }

    /**
     * Sync units from Accred API.
     * Triggers background task to fetch and upsert all units and principal users.
     */
    async function syncUnitsFromAccred(target_year: number): Promise<void> {
      if (loading.value) {
        throw new Error('Another operation is in progress');
      }

      loading.value = true;
      error.value = null;

      try {
        await api
          .post('sync/units', {
            json: { target_year },
          })
          .json();
      } catch (err: unknown) {
        if (err instanceof Error) {
          error.value = err.message ?? 'Failed to sync units from Accred API';
        } else {
          error.value = 'Failed to sync units from Accred API';
        }
        throw err;
      } finally {
        loading.value = false;
      }
    }

    /**
     * Get successful jobs from a specific year, filtered by module type and target type.
     * Returns only jobs that have state = FINISHED (3) and result = SUCCESS (0).
     */
    async function getPreviousYearSuccessfulJobs(
      year: number,
      moduleTypeId: number,
      targetType: TargetType,
    ): Promise<SyncJobResponse[]> {
      try {
        const jobs = (await api
          .get(`sync/jobs/year/${year}/latest`)
          .json()) as SyncJobResponse[];

        const result = jobs.filter(
          (job) =>
            job.module_type_id === moduleTypeId &&
            job.target_type === targetType &&
            job.state === IngestionState.FINISHED && // FINISHED
            job.result === IngestionResult.SUCCESS, // SUCCESS
        );
        return result;
      } catch (err: unknown) {
        console.error('Failed to fetch previous year jobs:', err);
        return [];
      }
    }

    async function reset(): Promise<void> {
      loading.value = false;
      error.value = null;
      // Reset syncJobs by clearing all properties
      Object.keys(syncJobs.value).forEach((key) => delete syncJobs.value[key]);
      currentYear.value = null;
      unsubscribeFromJobUpdates();
    }

    return {
      loading,
      error,
      syncJobs,
      currentYear,
      syncJobStatuses,
      getSyncStatusByModule,
      getSyncStateByModule,
      getSyncResultByModule,
      getLatestJobsByYear,
      isJobFinished,
      hasJobSucceeded,
      getSuccessRate,
      getResultLabel,
      fetchSyncJobsByYear,
      fetchLatestSyncJobsByYear,
      getPreviousYearSuccessfulJobs,
      initiateSync,
      subscribeToJobUpdates,
      unsubscribeFromJobUpdates,
      reset,
      syncUnitsFromAccred,
    };
  },
);
