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

export interface SyncJobStatus {
  module_type_id: number;
  year: number;
  status: number; // 0: pending, 1: in_progress, 2: completed, 3: failed
  provider_type: string;
}

export const useBackofficeDataManagement = defineStore(
  'backofficeDataManagement',
  () => {
    // State
    const loading = ref(false);
    const error = ref<string | null>(null);
    const syncJobs = reactive<Record<string, DataIngestionJob[]>>({}); // Initialize as empty object
    const currentYear = ref<number | null>(null);

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

    async function initiateSync(
      module_type_id: number,
      year: number,
      // provider_type: 'csv_upload' | 'tableau_api' | 'manual_entry',
      provider_type: 'csv' | 'api',
      target_type: 'data_entries' | 'factors' = 'data_entries',
      filters?: Record<string, unknown>,
      config?: Record<string, unknown>,
    ): Promise<number> {
      if (loading.value) throw new Error('Another operation is in progress');

      loading.value = true;
      error.value = null;

      try {
        const response = (await api
          .post(`sync/data-entries/${module_type_id}`, {
            json: {
              // to be aligned with backend enums // todo: retrieve enum from backend
              ingestion_method: provider_type === 'api' ? 0 : 1, // 0: api, 1: csv
              target_type: target_type === 'data_entries' ? 0 : 1,
              year,
              filters: filters || {},
              config: config || {},
            },
          })
          .json()) as { job_id: number };

        // Update local state with new job
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

    async function reset(): Promise<void> {
      loading.value = false;
      error.value = null;
      // Reset syncJobs by clearing all properties
      Object.keys(syncJobs).forEach((key) => delete syncJobs[key]);
      currentYear.value = null;
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
      reset,
      getModuleTypeId,
    };
  },
);
