import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from 'src/api/http';
import {
  MODULE_SUBMODULES,
  type SubmoduleConfig as ModuleUploadConfig,
  type SubmoduleConfig as StaticSubmoduleConfig,
} from 'src/constant/backoffice-module-config';
import { type Module } from 'src/constant/modules';

export interface FileMetadata {
  path: string;
  filename: string;
  uploaded_at: string;
  rows_processed?: number;
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
  inputs_deactivated?: boolean;
  latest_data_job?: SyncJobSummary | null;
  latest_api_data_job?: SyncJobSummary | null;
  latest_factor_job?: SyncJobSummary | null;
  latest_reference_job?: SyncJobSummary | null;
  /**
   * Issue #1215 — backend-computed "Incomplete" flag. True iff a
   * mandatory upload (factor or reference) is missing. Frontend
   * renders this directly instead of re-deriving from latest_* jobs.
   */
  incomplete?: boolean;
  incomplete_reasons?: string[];
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
  latest_common_data_job?: SyncJobSummary | null;
  latest_common_factor_job?: SyncJobSummary | null;
  /** Issue #1215 — module-level "Incomplete" rollup (backend-computed). */
  incomplete?: boolean;
}

export interface UnifiedModuleConfig {
  enabled: boolean;
  uncertainty_tag: 'low' | 'medium' | 'high' | 'none';
  submodules: Record<string, UnifiedSubmoduleConfig>;
  latest_common_data_job?: SyncJobSummary | null;
  latest_common_factor_job?: SyncJobSummary | null;
  /** Issue #1215 — module-level "Incomplete" rollup (backend-computed). */
  incomplete?: boolean;
}

export interface UnifiedSubmoduleConfig extends SubmoduleConfig {
  key: string;
  labelKey: string;
  moduleTypeId: number;
  dataEntryTypeId?: number;
}

export interface RecalculationStatusEntry {
  module_type_id: number;
  data_entry_type_id: number;
  year: number;
  needs_recalculation: boolean;
  last_factor_job_id?: number | null;
  last_factor_job_result?: number | null;
  last_recalculation_job_id?: number | null;
  last_recalculation_job_result?: number | null;
}

export interface ModuleRecalculationStatusEntry {
  module_type_id: number;
  year: number;
  needs_recalculation: boolean;
  data_entry_types: RecalculationStatusEntry[];
}

interface YearConfig {
  modules: Record<string, ModuleConfig>;
  reduction_objectives: ReductionObjectives;
}

export interface YearConfigurationResponse {
  year: number;
  is_started: boolean;
  /**
   * #1234-followup — ISO timestamp when ``unit_sync`` finished SUCCESS
   * for this year. ``null`` while the pipeline is still running or
   * before it ever ran; backend ``/dispatch`` refuses uploads while
   * ``null``. The data-management page surfaces a banner + disables
   * upload affordances on the null state.
   */
  configuration_completed?: string | null;
  config: YearConfig;
  recalculation_status: ModuleRecalculationStatusEntry[];
  updated_at: string;
  /**
   * Issue #867 — populated by ``POST /year-configuration/{year}`` when
   * the endpoint auto-enqueues the ``unit_sync`` pipeline alongside the
   * row create.  ``GET`` responses leave it ``null`` (the active
   * pipeline_id for a running job lives in the unified
   * ``pipelineState`` store sourced from
   * ``GET /v1/sync/active-pipelines``).
   */
  pipeline_id?: string | null;
}

/** Lightweight row from `GET /year-configuration/` (workspace year selector). */
export interface YearConfigurationListItem {
  year: number;
  is_started: boolean;
  /** #1234-followup — see YearConfigurationResponse.configuration_completed. */
  configuration_completed?: string | null;
  updated_at: string;
}

interface YearConfigurationCreate {
  is_started?: boolean;
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
  /** All year-configuration rows visible to the caller (workspace year selector). */
  const configuredYears = ref<YearConfigurationListItem[]>([]);

  /**
   * Set of years that are globally open (`is_started`). The list endpoint
   * already filters these for regular users; admins receive every row, so we
   * re-filter client-side to keep the meaning identical for both.
   */
  const startedYears = computed(
    () =>
      new Set(
        configuredYears.value.filter((y) => y.is_started).map((y) => y.year),
      ),
  );

  /** Fetch the list of year-configuration rows (global, not unit-scoped). */
  async function fetchConfiguredYears(): Promise<YearConfigurationListItem[]> {
    const rows = (await api
      .get('year-configuration/')
      .json()) as YearConfigurationListItem[];
    configuredYears.value = rows;
    return rows;
  }

  // Methods
  async function fetchConfig(
    year: number,
  ): Promise<YearConfigurationResponse | null> {
    loading.value = true;
    notFound.value = false;

    try {
      // Suppress the global 404 error toast: a missing year-configuration is
      // expected on first visit and is rendered as a "Create year" empty-state
      // by the caller. Non-404 errors still surface via the global handler.
      const response = (await api
        .get(`year-configuration/${year}`, { skipErrorCodes: [404] })
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
      // Issue #867 — the response now carries ``pipeline_id`` (UUID of
      // the unit_sync pipeline auto-enqueued by the backend).  The
      // caller subscribes to it via ``usePipelineStream``; no extra
      // store state is needed.
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
          inputs_deactivated: false,
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

  function getModuleUncertaintyTag(
    module: Module,
  ): 'low' | 'medium' | 'high' | 'none' | null {
    const config = getModule(module);
    return config?.uncertainty_tag ?? null;
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
  /**
   * Flip a year's `is_started` flag to true, making it visible to non-admin
   * users in their workspace year selector. Thin wrapper over updateConfig
   * so callers don't need to know the payload shape.
   */
  async function openForUsers(
    year: number,
  ): Promise<YearConfigurationResponse> {
    return updateConfig(year, { is_started: true });
  }

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

  function isSubmoduleInputsDeactivated(sub: ModuleUploadConfig): boolean {
    const subKey =
      sub.dataEntryTypeId !== undefined
        ? String(sub.dataEntryTypeId)
        : undefined;
    if (!subKey) return false;
    const mod = config.value?.config?.modules?.[String(sub.moduleTypeId)];
    return mod?.submodules?.[subKey]?.inputs_deactivated ?? false;
  }

  /** True when reduction objectives goals or CSV files are not fully configured. */
  const isReductionObjectiveIncomplete = computed(() => {
    if (!config.value) return false;
    const ro = config.value.config?.reduction_objectives;
    if (!ro) return true;
    const hasGoal = ro.goals.some(
      (g) => g.target_year > 0 && g.reference_year > 0,
    );
    const files = ro.files;
    const allFilesUploaded =
      !!files?.institutional_footprint &&
      !!files?.population_projections &&
      !!files?.unit_scenarios;
    return !hasGoal || !allFilesUploaded;
  });

  /**
   * Issue #1215 — module-level "Incomplete" comes from the backend
   * (disabled modules carry ``incomplete=false``); OR with the
   * still-frontend reduction-objectives flag.
   */
  const anyModuleIncomplete = computed(() => {
    if (!config.value) return false;
    const modules = config.value.config?.modules ?? {};
    const anyModule = Object.values(modules).some((m) => !!m?.incomplete);
    return anyModule || isReductionObjectiveIncomplete.value;
  });

  function getModuleConfig(module: Module): ModuleConfig | null {
    const moduleTypeIdMap = buildModuleTypeIdMapping();
    const targetTypeId = moduleTypeIdMap[module];
    if (!targetTypeId) return null;

    const backendKey = String(targetTypeId);
    return config.value?.config?.modules?.[backendKey] ?? null;
  }

  const recalculationStatus = computed<
    Record<number, ModuleRecalculationStatusEntry>
  >(() => {
    const map: Record<number, ModuleRecalculationStatusEntry> = {};
    for (const s of config.value?.recalculation_status ?? []) {
      map[s.module_type_id] = s;
    }
    return map;
  });

  function getRecalcStatus(
    moduleTypeId: number,
    dataEntryTypeId?: number,
  ): RecalculationStatusEntry | undefined {
    if (dataEntryTypeId === undefined) return undefined;
    return recalculationStatus.value[moduleTypeId]?.data_entry_types.find(
      (d) => d.data_entry_type_id === dataEntryTypeId,
    );
  }

  return {
    // State
    config,
    loading,
    notFound,
    configuredYears,
    // Computed
    startedYears,
    anyModuleIncomplete,
    isReductionObjectiveIncomplete,
    unifiedModuleConfig,
    visibleModules,
    recalculationStatus,
    // Helpers
    getModule,
    getSubmodule,
    getModuleNameFromSubmodule,
    getModuleConfig,
    getRecalcStatus,
    isModuleVisible,
    isSubmoduleVisible,
    isModuleEnabled,
    isSubmoduleEnabled,
    isSubmoduleInputsDeactivated,
    getModuleUncertaintyTag,
    // Methods
    fetchConfig,
    fetchConfiguredYears,
    createConfig,
    updateConfig,
    openForUsers,
  };
});
