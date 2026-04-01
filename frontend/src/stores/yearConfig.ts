import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from 'src/api/http';

export interface FileMetadata {
  path: string;
  filename: string;
  uploaded_at: string;
}

export interface ReductionObjectiveGoal {
  target_year: number;
  reduction_percentage: number;
  reference_year: number;
}

export interface ReductionObjectives {
  files: {
    institutional_footprint: FileMetadata | null;
    population_projections: FileMetadata | null;
    unit_scenarios: FileMetadata | null;
  };
  goals: ReductionObjectiveGoal[];
}

export interface SubmoduleConfig {
  enabled: boolean;
  threshold: number | null;
}

export interface ModuleConfig {
  enabled: boolean;
  uncertainty_tag: 'low' | 'medium' | 'high' | 'none';
  submodules: Record<string, SubmoduleConfig>;
}

export interface YearConfig {
  modules: Record<string, ModuleConfig>;
  reduction_objectives: ReductionObjectives;
}

export interface YearConfigurationResponse {
  year: number;
  is_started: boolean;
  is_reports_synced: boolean;
  config: YearConfig;
  updated_at: string;
}

export interface YearConfigurationCreate {
  is_started?: boolean;
  is_reports_synced?: boolean;
  config?: Partial<YearConfig>;
}

export interface YearConfigurationUpdate {
  is_started?: boolean;
  is_reports_synced?: boolean;
  config?: {
    modules?: Record<string, ModuleConfig>;
    reduction_objectives?: Partial<ReductionObjectives>;
  };
}

export interface FileUploadResponse {
  success: boolean;
  file: FileMetadata;
  message: string;
}

export type FileCategory = 'footprint' | 'population' | 'scenarios';

export const useYearConfigStore = defineStore('yearConfig', () => {
  // State
  const config = ref<YearConfigurationResponse | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const currentYear = ref<number | null>(null);
  /** True when the backend returned 404 — no configuration exists yet for this year. */
  const notFound = ref(false);

  // Methods
  async function fetchConfig(
    year: number,
  ): Promise<YearConfigurationResponse | null> {
    loading.value = true;
    error.value = null;
    notFound.value = false;
    currentYear.value = year;

    try {
      const response = (await api
        .get(`year-configuration/${year}`)
        .json()) as YearConfigurationResponse;
      config.value = response;
      return response;
    } catch (err: unknown) {
      if (err instanceof Error && 'response' in err) {
        const httpErr = err as Error & { response: { status: number } };
        if (httpErr.response?.status === 404) {
          notFound.value = true;
          config.value = null;
          return null;
        }
      }
      error.value =
        err instanceof Error ? err.message : 'Failed to fetch configuration';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function createConfig(
    year: number,
    payload?: YearConfigurationCreate,
  ): Promise<YearConfigurationResponse> {
    loading.value = true;
    error.value = null;

    try {
      const response = (await api
        .post(`year-configuration/${year}`, {
          json: payload ?? {},
        })
        .json()) as YearConfigurationResponse;
      config.value = response;
      notFound.value = false;
      return response;
    } catch (err: unknown) {
      error.value =
        err instanceof Error ? err.message : 'Failed to create configuration';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function updateConfig(
    year: number,
    payload: YearConfigurationUpdate,
  ): Promise<YearConfigurationResponse> {
    loading.value = true;
    error.value = null;

    try {
      const response = (await api
        .patch(`year-configuration/${year}`, {
          json: payload,
        })
        .json()) as YearConfigurationResponse;
      config.value = response;
      return response;
    } catch (err: unknown) {
      if (err instanceof Error) {
        error.value = err.message ?? 'Failed to update configuration';
      } else {
        error.value = 'Failed to update configuration';
      }
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function uploadFile(
    year: number,
    category: FileCategory,
    file: File,
  ): Promise<FileUploadResponse> {
    loading.value = true;
    error.value = null;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('category', category);

    try {
      const response = (await api
        .post(`year-configuration/${year}/upload`, {
          body: formData,
        })
        .json()) as FileUploadResponse;

      // Refresh config after upload
      await fetchConfig(year);
      return response;
    } catch (err: unknown) {
      if (err instanceof Error) {
        error.value = err.message ?? 'Failed to upload file';
      } else {
        error.value = 'Failed to upload file';
      }
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function checkThreshold(
    year: number,
    moduleTypeId: number,
    dataEntryTypeId: number,
    value: number,
  ): Promise<{ exceeded: boolean; threshold: number | null; value: number }> {
    try {
      const response = (await api
        .get('year-configuration/check-threshold', {
          searchParams: {
            year,
            module_type_id: moduleTypeId,
            data_entry_type_id: dataEntryTypeId,
            value,
          },
        })
        .json()) as {
        exceeded: boolean;
        threshold: number | null;
        value: number;
      };
      return response;
    } catch (err: unknown) {
      console.error('Failed to check threshold:', err);
      return { exceeded: false, threshold: null, value };
    }
  }

  function reset() {
    config.value = null;
    loading.value = false;
    error.value = null;
    currentYear.value = null;
    notFound.value = false;
  }

  return {
    // State
    config,
    loading,
    error,
    currentYear,
    notFound,
    // Methods
    fetchConfig,
    createConfig,
    updateConfig,
    uploadFile,
    checkThreshold,
    reset,
  };
});
