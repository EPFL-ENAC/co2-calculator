import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from 'src/api/http';
import {
  MODULE_SUBMODULES,
  MODULE_COMMON_UPLOADS,
  type SubmoduleConfig as ModuleUploadConfig,
} from 'src/constant/backoffice-module-config';
import { MODULES_LIST } from 'src/constant/modules';

interface FileMetadata {
  path: string;
  filename: string;
  uploaded_at: string;
}

export interface ReductionObjectiveGoal {
  target_year: number;
  reduction_percentage: number;
  reference_year: number;
}

interface ReductionObjectives {
  files: {
    institutional_footprint: FileMetadata | null;
    population_projections: FileMetadata | null;
    unit_scenarios: FileMetadata | null;
  };
  goals: ReductionObjectiveGoal[];
  institutional_footprint: [];
  population_projections: [];
  unit_scenarios: [];
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

interface YearConfig {
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

interface YearConfigurationCreate {
  is_started?: boolean;
  is_reports_synced?: boolean;
  config?: Partial<YearConfig>;
}

/** Partial module config allowing nested partial submodule updates. */
interface ModuleConfigUpdate {
  enabled?: boolean;
  uncertainty_tag?: ModuleConfig['uncertainty_tag'];
  submodules?: Record<string, Partial<SubmoduleConfig>>;
}

interface YearConfigurationUpdate {
  is_started?: boolean;
  is_reports_synced?: boolean;
  config?: {
    modules?: Record<string, ModuleConfigUpdate>;
    reduction_objectives?: Partial<ReductionObjectives>;
  };
}

export const useYearConfigStore = defineStore('yearConfig', () => {
  // State
  const config = ref<YearConfigurationResponse | null>(null);
  const loading = ref(false);
  /** True when the backend returned 404 — no configuration exists yet for this year. */
  const notFound = ref(false);

  // Methods
  async function fetchConfig(
    year: number,
  ): Promise<YearConfigurationResponse | null> {
    loading.value = true;
    notFound.value = false;

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

    try {
      const response = (await api
        .post(`year-configuration/${year}`, {
          json: payload ?? {},
        })
        .json()) as YearConfigurationResponse;
      config.value = response;
      notFound.value = false;
      return response;
    } finally {
      loading.value = false;
    }
  }

  async function updateConfig(
    year: number,
    payload: YearConfigurationUpdate,
  ): Promise<YearConfigurationResponse> {
    loading.value = true;

    try {
      const response = (await api
        .patch(`year-configuration/${year}`, {
          json: payload,
        })
        .json()) as YearConfigurationResponse;
      config.value = response;
      return response;
    } finally {
      loading.value = false;
    }
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
  };
});
