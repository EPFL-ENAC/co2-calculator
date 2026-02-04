import { defineStore } from 'pinia';
import { computed, reactive, ref } from 'vue';
import { api } from 'src/api/http';
import { Module } from 'src/constant/modules';

export interface DataIngestionJob {
  job_id: number;
  module_type_id: number;
  year: number;
  provider_type: string;
  target_type: number;
  status: number; // 0: pending, 1: in_progress, 2: completed, 3: failed
  status_message?: string;
  meta?: Record<string, unknown>;
}

export interface JobUpdatePayload {
  job_id: number;
  module_type_id: number;
  target_type: number;
  year: number | null;
  status: string | number;
  status_message: string;
}

export interface SyncJobStatus {
  module_type_id: number;
  year: number;
  status: number; // 0: pending, 1: in_progress, 2: completed, 3: failed
  provider_type: string;
}

export type InitiateSyncParams = {
  module_type_id: number;
  year?: number;
  provider_type: 'csv' | 'api';
  target_type?: 'data_entries' | 'factors';
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
    const syncJobs = reactive<Record<string, DataIngestionJob[]>>({}); // Initialize as empty object
    const currentYear = ref<number | null>(null);
    let sseConnection: EventSource | null = null;

    // Computed properties
    const syncJobStatuses = computed<SyncJobStatus[]>(() => {
      if (!currentYear.value) return [];

      const jobs = syncJobs[currentYear.value] || [];
      return jobs.map((job) => ({
        module_type_id: job.module_type_id,
        year: job.year,
        status: job.status,
        provider_type: job.provider_type,
      }));
    });

    const getSyncStatusByModule = (
      moduleType: Module,
      year: number,
    ): number => {
      const moduleTypeId = getModuleTypeId(moduleType);
      const jobs = syncJobs[year] || [];
      const job = jobs.find((j) => j.module_type_id === moduleTypeId);
      return job ? job.status : 0; // Default to pending (0) if no job found
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
        syncJobs[year] = response;
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
      target_type = 'data_entries',
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
          // to be aligned with backend enums // todo: retrieve enum from backend
          ingestion_method: provider_type === 'api' ? 0 : 1, // 0: api, 1: csv
          target_type: target_type === 'data_entries' ? 0 : 1,
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
          if (!syncJobs[year]) {
            syncJobs[year] = [];
          }
          syncJobs[year].push({
            job_id: response.job_id,
            module_type_id,
            year,
            provider_type,
            target_type: 0, // data_entries
            status: 0, // pending
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
            // debugger;
            const update: JobUpdatePayload = JSON.parse(event.data);
            console.log(update);
            // Map status codes to numbers
            // NOT_STARTED = 0
            // PENDING = 1
            // IN_PROGRESS = 2
            // COMPLETED = 3
            // FAILED = 4
            const statusMap: Record<string, number> = {
              NOT_STARTED: 0,
              PENDING: 1,
              IN_PROGRESS: 2,
              COMPLETED: 3,
              FAILED: 4,
            };

            const status =
              typeof update.status === 'number'
                ? update.status
                : (statusMap[update.status] ?? 0);

            const job_id = update.job_id;
            // const module_type_id = update.module_type_id;
            const year = update.year;

            console.log(
              `Received SSE update for job_id ${job_id}: status=${status}`,
            );
            // Find and update the job in the store
            if (syncJobs[year]) {
              const jobIndex = syncJobs[year].findIndex(
                (j) => j.job_id === job_id,
              );
              if (jobIndex !== -1) {
                syncJobs[year][jobIndex] = {
                  ...syncJobs[year][jobIndex],
                  status,
                  status_message: update.status_message || '',
                };
              }
            }

            if (status === 3) {
              console.log('Sync job completed: call onCompleted callback');
              onCompleted?.(update);
            }

            if (status === 4) {
              console.log('Sync job failed');
              onFail?.(update);
            }
            if (status === 3 || status === 4) {
              unsubscribeFromJobUpdates();
            }
          } catch (err) {
            console.error('Error parsing SSE message:', err);
          }
        };

        sseConnection.onerror = () => {
          console.error('SSE connection error');
          unsubscribeFromJobUpdates();
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
        // debugger;
        console.log('Closing SSE connection');
        sseConnection.close();
        sseConnection = null;
      }
    }

    async function reset(): Promise<void> {
      loading.value = false;
      error.value = null;
      // Reset syncJobs by clearing all properties
      Object.keys(syncJobs).forEach((key) => delete syncJobs[key]);
      currentYear.value = null;
      unsubscribeFromJobUpdates();
    }

    // Helper function to get module type ID from module
    function getModuleTypeId(module: Module): number {
      const moduleTypeIds: Record<Module, number> = {
        'my-lab': 1,
        'professional-travel': 2,
        infrastructure: 3,
        'equipment-electric-consumption': 4,
        purchase: 5,
        'internal-services': 6,
        'external-cloud-and-ai': 7,
      };
      return moduleTypeIds[module];
    }

    return {
      loading,
      error,
      syncJobs,
      currentYear,
      syncJobStatuses,
      getSyncStatusByModule,
      fetchSyncJobsByYear,
      initiateSync,
      subscribeToJobUpdates,
      unsubscribeFromJobUpdates,
      reset,
      getModuleTypeId,
    };
  },
);
