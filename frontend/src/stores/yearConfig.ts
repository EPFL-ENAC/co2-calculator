import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from 'src/api/http';
import {
  MODULE_SUBMODULES,
  MODULE_COMMON_UPLOADS,
  type SubmoduleConfig as ModuleUploadConfig,
  type SubmoduleConfig as StaticSubmoduleConfig,
} from 'src/constant/backoffice-module-config';
import { MODULES_LIST, type Module } from 'src/constant/modules';

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

export interface UnifiedModuleConfig {
  enabled: boolean;
  uncertainty_tag: 'low' | 'medium' | 'high' | 'none';
  submodules: Record<string, UnifiedSubmoduleConfig>;
}

export interface UnifiedSubmoduleConfig extends SubmoduleConfig {
  key: string;
  labelKey: string;
  moduleTypeId: number;
  dataEntryTypeId?: number;
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

  // ── Unified module config helper ────────────────────────────────────────────

  function buildModuleTypeIdMapping(): Partial<Record<Module, number>> {
    const mapping: Partial<Record<Module, number>> = {};
    for (const modName of Object.keys(MODULE_SUBMODULES) as Module[]) {
      const subs = MODULE_SUBMODULES[modName];
      if (subs && subs.length > 0) {
        mapping[modName] = subs[0].moduleTypeId;
      }
    }
    return mapping;
  }

  function invertMapping(
    mapping: Partial<Record<Module, number>>,
  ): Record<number, Module> {
    const inverted: Record<number, Module> = {} as Record<number, Module>;
    for (const [moduleName, typeId] of Object.entries(mapping)) {
      inverted[typeId] = moduleName as Module;
    }
    return inverted;
  }

  function mergeSubmoduleConfigs(
    backendSubmodules: Record<string, SubmoduleConfig>,
    staticSubmodules: StaticSubmoduleConfig[],
  ): Record<string, UnifiedSubmoduleConfig> {
    const merged: Record<string, UnifiedSubmoduleConfig> = {};

    for (const staticSub of staticSubmodules) {
      const subKey =
        staticSub.dataEntryTypeId !== undefined
          ? String(staticSub.dataEntryTypeId)
          : staticSub.key;
      const backendSub = backendSubmodules[subKey];

      if (backendSub) {
        merged[staticSub.key] = {
          ...backendSub,
          key: staticSub.key,
          labelKey: staticSub.labelKey,
          moduleTypeId: staticSub.moduleTypeId,
          dataEntryTypeId: staticSub.dataEntryTypeId,
        };
      } else {
        merged[staticSub.key] = {
          enabled: true,
          threshold: null,
          key: staticSub.key,
          labelKey: staticSub.labelKey,
          moduleTypeId: staticSub.moduleTypeId,
          dataEntryTypeId: staticSub.dataEntryTypeId,
        };
      }
    }

    return merged;
  }

  /**
   * Merged module config keyed by FRONTEND module names.
   * Combines backend runtime config with static submodule definitions.
   */
  const unifiedModuleConfig = computed(() => {
    if (!config.value?.config?.modules) return {};

    const mapping = buildModuleTypeIdMapping();
    const reverseMapping = invertMapping(mapping);

    return Object.fromEntries(
      Object.entries(config.value.config.modules).map(
        ([backendId, modConfig]) => {
          const moduleName = reverseMapping[parseInt(backendId)];
          if (!moduleName) return [backendId, modConfig];

          const staticSubmodules = MODULE_SUBMODULES[moduleName] || [];
          const unifiedSubmodules = mergeSubmoduleConfigs(
            modConfig.submodules,
            staticSubmodules,
          );

          return [
            moduleName,
            {
              ...modConfig,
              submodules: unifiedSubmodules,
            },
          ];
        },
      ),
    );
  });

  /** Get unified config for a module by frontend name. */
  function getModule(moduleName: Module): UnifiedModuleConfig | null {
    return (
      (unifiedModuleConfig.value[moduleName] as UnifiedModuleConfig) || null
    );
  }

  /** Get unified config for a submodule by module and submodule key. */
  function getSubmodule(
    moduleName: Module,
    subKey: string,
  ): UnifiedSubmoduleConfig | null {
    return (
      (unifiedModuleConfig.value[moduleName]?.submodules[
        subKey
      ] as UnifiedSubmoduleConfig) || null
    );
  }

  /** Get module name from a submodule config. */
  function getModuleNameFromSubmodule(sub: ModuleUploadConfig): Module | null {
    for (const moduleName of Object.keys(MODULE_SUBMODULES) as Module[]) {
      const subs = MODULE_SUBMODULES[moduleName];
      if (subs?.some((s) => s.key === sub.key)) {
        return moduleName;
      }
    }
    return null;
  }

  // ── Module visibility helpers ───────────────────────────────────────────────

  /** Check if a module is enabled and visible to users. */
  function isModuleVisible(module: Module): boolean {
    const config = getModule(module);
    return config?.enabled ?? false;
  }

  /** Check if a submodule is enabled and visible. */
  function isSubmoduleVisible(moduleName: Module, subKey: string): boolean {
    const sub = getSubmodule(moduleName, subKey);
    return sub?.enabled ?? false;
  }

  /** Get list of currently visible (enabled) modules in timeline order. */
  const visibleModules = computed(() => {
    if (!config.value?.config?.modules) return [];
    return Object.keys(unifiedModuleConfig.value).filter((key) => {
      const modConfig = unifiedModuleConfig.value[key] as UnifiedModuleConfig;
      return modConfig?.enabled ?? false;
    }) as Module[];
  });

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

  function getModuleConfig(module: Module): ModuleConfig | null {
    const moduleTypeIdMap = buildModuleTypeIdMapping();
    const targetTypeId = moduleTypeIdMap[module];
    if (!targetTypeId) return null;

    const backendKey = String(targetTypeId);
    return config.value?.config?.modules?.[backendKey] ?? null;
  }

  return {
    // State
    config,
    loading,
    notFound,
    // Computed
    latestJobs,
    anyModuleIncomplete,
    unifiedModuleConfig,
    visibleModules,
    // Helpers
    getModule,
    getSubmodule,
    getModuleNameFromSubmodule,
    getModuleConfig,
    isModuleVisible,
    isSubmoduleVisible,
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
