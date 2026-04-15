import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from 'src/api/http';
import {
  MODULE_SUBMODULES,
  MODULE_COMMON_UPLOADS,
  type SubmoduleConfig as ModuleUploadConfig,
} from 'src/constant/backoffice-module-config';
import { MODULES_LIST } from 'src/constant/modules';

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
  latest_job?: SyncJobSummary | null;
}

export interface SyncJobSummary {
  job_id: number;
  module_type_id?: number;
  data_entry_type_id?: number;
  year?: number;
  ingestion_method: number;
  target_type?: number;
  state?: number;
  result?: number;
  status_message?: string;
  meta?: Record<string, unknown>;
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
  latest_jobs: SyncJobSummary[];
  updated_at: string;
}

export interface YearConfigurationCreate {
  is_started?: boolean;
  is_reports_synced?: boolean;
  config?: Partial<YearConfig>;
}

/** Partial module config allowing nested partial submodule updates. */
export interface ModuleConfigUpdate {
  enabled?: boolean;
  uncertainty_tag?: ModuleConfig['uncertainty_tag'];
  submodules?: Record<string, Partial<SubmoduleConfig>>;
}

export interface YearConfigurationUpdate {
  is_started?: boolean;
  is_reports_synced?: boolean;
  config?: {
    modules?: Record<string, ModuleConfigUpdate>;
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

  /** All current ingestion jobs for the loaded year. */
  const latestJobs = computed<SyncJobSummary[]>(
    () => config.value?.latest_jobs ?? [],
  );

  // ── Completeness helpers ────────────────────────────────────────────────────

  function isModuleEnabled(module: string): boolean {
    const subs =
      MODULE_SUBMODULES[module as keyof typeof MODULE_SUBMODULES] ?? [];
    const moduleTypeId = subs.length > 0 ? subs[0].moduleTypeId : 0;
    if (!moduleTypeId) return true;
    return (
      config.value?.config?.modules?.[String(moduleTypeId)]?.enabled ?? true
    );
  }

  function isSubmoduleEnabled(sub: ModuleUploadConfig): boolean {
    const subKey =
      sub.dataEntryTypeId !== undefined
        ? String(sub.dataEntryTypeId)
        : undefined;
    if (!subKey) return true;
    const mod = config.value?.config?.modules?.[String(sub.moduleTypeId)];
    return mod?.submodules?.[subKey]?.enabled ?? true;
  }

  function _preferredIngestionMethods(targetType: 0 | 1): string[] {
    if (targetType === 1) {
      return ['CSV', 'COMPUTED'];
    }
    return ['CSV', 'API', 'COMPUTED'];
  }

  function _pickLatestJobByIngestionMethod(
    candidates: (typeof latestJobs.value)[number][],
    targetType: 0 | 1,
  ) {
    const preferredMethods = _preferredIngestionMethods(targetType);
    for (const method of preferredMethods) {
      const job = candidates.find(
        (candidate) =>
          String(candidate.ingestion_method ?? '').toUpperCase() === method,
      );
      if (job) return job;
    }
    return candidates[0];
  }

  function _latestJob(sub: ModuleUploadConfig, targetType: 0 | 1) {
    const candidates = latestJobs.value.filter(
      (j) =>
        j.module_type_id === sub.moduleTypeId && j.target_type === targetType,
    );
    const scopedCandidates =
      sub.dataEntryTypeId !== undefined
        ? candidates.filter(
            (j) => (j.data_entry_type_id ?? undefined) === sub.dataEntryTypeId,
          )
        : candidates;

    // Prefer the ingestion method used for completeness checks instead of
    // relying on API ordering when multiple current jobs exist.
    return _pickLatestJobByIngestionMethod(scopedCandidates, targetType);
  }

  function isSubmoduleIncomplete(sub: ModuleUploadConfig): boolean {
    if (!sub.noFactors) {
      const job = _latestJob(sub, 1);
      if (!job || job.result !== 0) return true;
    }
    if (sub.other) {
      const job = _latestJob(sub, 0);
      if (!job || job.result !== 0) return true;
    }
    return false;
  }

  function isModuleIncomplete(module: string): boolean {
    if (!isModuleEnabled(module)) return false;
    const submodules =
      MODULE_SUBMODULES[module as keyof typeof MODULE_SUBMODULES] ?? [];
    const commonUploads =
      MODULE_COMMON_UPLOADS[module as keyof typeof MODULE_COMMON_UPLOADS] ?? [];
    if (submodules.length === 0 && commonUploads.length === 0) return false;
    return (
      submodules.some(
        (sub) => isSubmoduleEnabled(sub) && isSubmoduleIncomplete(sub),
      ) || commonUploads.some((common) => isSubmoduleIncomplete(common))
    );
  }

  /** True when any enabled module has mandatory uploads missing or failed. */
  const anyModuleIncomplete = computed(
    () => !!config.value && MODULES_LIST.some((m) => isModuleIncomplete(m)),
  );

  return {
    // State
    config,
    loading,
    error,
    currentYear,
    notFound,
    // Computed
    latestJobs,
    anyModuleIncomplete,
    // Completeness helpers
    isModuleEnabled,
    isSubmoduleEnabled,
    isModuleIncomplete,
    isSubmoduleIncomplete,
    // Methods
    fetchConfig,
    createConfig,
    updateConfig,
    uploadFile,
    checkThreshold,
    reset,
  };
});
