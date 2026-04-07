import { defineStore } from 'pinia';
import { computed, reactive, ref } from 'vue';
import { MODULES, Module } from 'src/constant/modules';
import { api } from 'src/api/http';
import {
  MODULE_STATES,
  ModuleState,
  ModuleStates,
  getModuleTypeId,
  getModuleFromTypeId,
} from 'src/constant/moduleStates';

import type {
  AllSubmoduleTypes,
  ModuleResponse,
  Submodule,
  TaxonomyNode,
} from 'src/constant/modules';
import { useRoute } from 'vue-router';

/**
 * API response for validated totals endpoint.
 * `modules` maps module_type_id to its display value
 * (FTE for headcount, tonnes CO₂eq for others).
 */
interface ValidatedTotalsResponse {
  modules: Record<number, number>;
  total_tonnes_co2eq: number;
  total_fte: number;
}

interface YearlyValidatedEmission {
  year: number;
  total_tonnes_co2eq: number;
}

export interface EmissionBreakdownResponse {
  module_breakdown: EmissionBreakdownCategoryRow[];
  additional_breakdown: EmissionBreakdownCategoryRow[];
  per_person_breakdown: Record<string, number>;
  validated_categories: string[];
  headcount_validated: boolean;
  total_tonnes_co2eq: number;
  total_fte: number;
}

export interface EmissionBreakdownValue {
  emission_type: string;
  key: string;
  value: number;
  parent_key?: string;
}

export interface EmissionBreakdownCategoryRow {
  category: string;
  category_key: string;
  emissions: EmissionBreakdownValue[];
  [key: string]: unknown;
}

/**
 * API response for inventory module
 */
interface CarbonReportModuleResponse {
  id: number;
  inventory_id: number;
  module_type_id: number;
  status: number;
}

export const useTimelineStore = defineStore('timeline', () => {
  // Initialize all modules with default status
  const itemStates = reactive<ModuleStates>({
    [MODULES.Headcount]: MODULE_STATES.Default,
    [MODULES.ProfessionalTravel]: MODULE_STATES.Default,
    [MODULES.Buildings]: MODULE_STATES.Default,
    [MODULES.EquipmentElectricConsumption]: MODULE_STATES.Default,
    [MODULES.Purchase]: MODULE_STATES.Default,
    [MODULES.ResearchFacilities]: MODULE_STATES.Default,
    [MODULES.ExternalCloudAndAI]: MODULE_STATES.Default,
    [MODULES.ProcessEmissions]: MODULE_STATES.Default,
    [MODULES.Commuting]: MODULE_STATES.Default,
    [MODULES.Food]: MODULE_STATES.Default,
    [MODULES.Waste]: MODULE_STATES.Default,
    [MODULES.EmbodiedEnergy]: MODULE_STATES.Default,
  });

  const loading = ref(false);
  const error = ref<string | null>(null);
  const currentCarbonReportId = ref<number | null>(null);
  const $route = useRoute();
  const currentModuleType = computed(() => $route.params.module as Module);

  const currentCarbonReportModuleState = computed(() => {
    return itemStates[currentModuleType.value];
  });

  const currentCarbonReportModuleEdit = computed(() => {
    return (
      currentCarbonReportModuleState.value === MODULE_STATES.Default ||
      currentCarbonReportModuleState.value === MODULE_STATES.InProgress
    );
  });
  /**
   * Fetch module statuses from the API for a given carbon report.
   * This should be called when a carbon report is selected.
   */
  async function fetchModuleStates(carbonReportId: number) {
    loading.value = true;
    error.value = null;
    currentCarbonReportId.value = carbonReportId;

    try {
      const response = (await api
        .get(`carbon-reports/${carbonReportId}/modules/`)
        .json()) as CarbonReportModuleResponse[];

      // Update itemStates from API response
      for (const mod of response) {
        const moduleKey = getModuleFromTypeId(mod.module_type_id);
        if (moduleKey) {
          itemStates[moduleKey] = mod.status as ModuleState;
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        error.value = err.message ?? 'Failed to fetch module states';
      } else {
        error.value = 'Failed to fetch module states';
      }
      // Keep current states on error
    } finally {
      loading.value = false;
    }
  }

  /**
   * Update the status of a module via API and update local state.
   * Displays error to user on failure (no retry).
   */
  async function setState(id: Module, state: ModuleState) {
    if (!currentCarbonReportId.value) {
      error.value = 'No carbon report selected';
      return;
    }

    const moduleTypeId = getModuleTypeId(id);
    const previousState = itemStates[id];

    // Optimistic update
    itemStates[id] = state;
    error.value = null;

    try {
      await api
        .patch(
          `carbon-reports/${currentCarbonReportId.value}/modules/${moduleTypeId}/status`,
          {
            json: { status: state },
          },
        )
        .json();
      await fetchModuleStates(currentCarbonReportId.value);
      useModuleStore().invalidateValidatedTotals();
      useModuleStore().invalidateEmissionBreakdown();
    } catch (err: unknown) {
      // Revert on error
      itemStates[id] = previousState;
      if (err instanceof Error) {
        error.value = err.message ?? 'Failed to update module status';
      } else {
        error.value = 'Failed to update module status';
      }
    }
  }

  /**
   * Reset the store state (e.g., when changing carbon report)
   */
  function reset() {
    currentCarbonReportId.value = null;
    error.value = null;
    // Reset all states to default
    for (const key of Object.keys(itemStates) as Module[]) {
      itemStates[key] = MODULE_STATES.Default;
    }
  }

  return {
    itemStates,
    loading,
    error,
    currentCarbonReportId,
    fetchModuleStates,
    setState,
    reset,
    currentState: currentCarbonReportModuleState,
    canEdit: currentCarbonReportModuleEdit,
  };
});

export const useModuleStore = defineStore('modules', () => {
  const state = reactive<{
    loading: boolean;
    error: string | null;
    data: ModuleResponse | null;
    taxonomy: TaxonomyNode | null;
    expandedSubmodules: Record<string, boolean>; // key: submodule ID
    loadingSubmodule: Record<string, boolean>; // key: submodule ID
    errorSubmodule: Record<string, string | null>; // key: submodule ID
    dataSubmodule: Record<string, Submodule | null>; // key: submodule ID
    taxonomySubmodule: Record<string, TaxonomyNode | null>; // key: submodule ID
    filterTermSubmodule: Record<string, string>; // key: submodule ID
    paginationSubmodule: Record<
      string,
      {
        page: number;
        rowsPerPage: number;
        sortBy?: string;
        descending?: boolean;
        rowsNumber?: number;
      }
    >; // key: submodule ID
    loadedSubmodules: Record<string, boolean>; // key: submodule ID
    travelStatsByClass: Array<Record<string, unknown>>;
    loadingTravelStatsByClass: boolean;
    errorTravelStatsByClass: string | null;
    travelEvolutionOverTime: Array<Record<string, unknown>>;
    loadingTravelEvolutionOverTime: boolean;
    errorTravelEvolutionOverTime: string | null;
    topClassBreakdown: Array<Record<string, unknown>>;
    loadingTopClassBreakdown: boolean;
    errorTopClassBreakdown: string | null;
    validatedTotals: ValidatedTotalsResponse | null;
    loadingValidatedTotals: boolean;
    errorValidatedTotals: string | null;
    yearlyValidatedEmissions: YearlyValidatedEmission[];
    loadingYearlyValidatedEmissions: boolean;
    errorYearlyValidatedEmissions: string | null;
    emissionBreakdown: EmissionBreakdownResponse | null;
    loadingEmissionBreakdown: boolean;
    errorEmissionBreakdown: string | null;
  }>({
    loading: false,
    error: null,
    data: null,
    taxonomy: null,
    filterTermSubmodule: reactive({}),
    expandedSubmodules: reactive({}),
    loadingSubmodule: reactive({}),
    errorSubmodule: reactive({}),
    dataSubmodule: reactive({}),
    taxonomySubmodule: reactive({}),
    paginationSubmodule: reactive({}),
    loadedSubmodules: reactive({}),
    travelStatsByClass: [],
    loadingTravelStatsByClass: false,
    errorTravelStatsByClass: null,
    travelEvolutionOverTime: [],
    loadingTravelEvolutionOverTime: false,
    errorTravelEvolutionOverTime: null,
    topClassBreakdown: [],
    loadingTopClassBreakdown: false,
    errorTopClassBreakdown: null,
    validatedTotals: null,
    loadingValidatedTotals: false,
    errorValidatedTotals: null,
    yearlyValidatedEmissions: [],
    loadingYearlyValidatedEmissions: false,
    errorYearlyValidatedEmissions: null,
    emissionBreakdown: null,
    loadingEmissionBreakdown: false,
    errorEmissionBreakdown: null,
  });
  function modulePath(moduleType: Module, unit: number, year: string) {
    const moduleTypeEncoded = encodeURIComponent(moduleType);
    const unitEncoded = encodeURIComponent(unit);
    const yearEncoded = encodeURIComponent(year);
    // Backend expects /{unit_id}/{year}/{module_id}
    const path = `modules/${unitEncoded}/${yearEncoded}/${moduleTypeEncoded}`;
    return path;
  }

  function initializeSubmoduleState(submoduleId: string) {
    if (!(submoduleId in state.expandedSubmodules)) {
      state.expandedSubmodules[submoduleId] = false;
    }
    if (!(submoduleId in state.loadingSubmodule)) {
      state.loadingSubmodule[submoduleId] = false;
    }
    if (!(submoduleId in state.errorSubmodule)) {
      state.errorSubmodule[submoduleId] = null;
    }
    if (!(submoduleId in state.dataSubmodule)) {
      state.dataSubmodule[submoduleId] = null;
    }
    if (!(submoduleId in state.taxonomySubmodule)) {
      state.taxonomySubmodule[submoduleId] = null;
    }
    // always initialize pagination with defaults
    state.paginationSubmodule[submoduleId] = {
      sortBy: undefined,
      descending: false,
      page: 1,
      rowsPerPage: 20,
      rowsNumber: 0,
    };
    if (!(submoduleId in state.loadedSubmodules)) {
      state.loadedSubmodules[submoduleId] = false;
    }
  }

  async function getModuleData(moduleType: Module, unit: number, year: string) {
    state.loading = true;
    state.error = null;
    state.data = null;
    try {
      state.data = (await api
        .get(modulePath(moduleType, unit, year))
        .json()) as ModuleResponse;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.error = err.message ?? 'Unknown error';
        state.data = null;
      } else {
        state.error = 'Unknown error';
        state.data = null;
      }
    } finally {
      state.loading = false;
    }
  }

  async function getModuleTotals(
    moduleType: Module,
    unit: number,
    year: string,
  ) {
    state.loading = true;
    state.error = null;
    try {
      const path = `${modulePath(moduleType, unit, year)}?preview_limit=0`;
      state.data = (await api.get(path).json()) as ModuleResponse;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.error = err.message ?? 'Unknown error';
      } else {
        state.error = 'Unknown error';
      }
    } finally {
      state.loading = false;
    }
  }

  async function getModuleTaxonomy(moduleType: Module) {
    state.loading = true;
    state.error = null;
    state.taxonomy = null;
    try {
      state.taxonomy = (await api
        .get(`taxonomies/module_type/${encodeURIComponent(moduleType)}`)
        .json()) as TaxonomyNode;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.error = err.message ?? 'Unknown error';
        state.taxonomy = null;
      } else {
        state.error = 'Unknown error';
        state.taxonomy = null;
      }
    } finally {
      state.loading = false;
    }
  }

  async function getSubmoduleData({
    moduleType,
    submoduleType,
    unit,
    year,
  }: {
    moduleType: Module;
    submoduleType: string;
    unit: number;
    year: string;
  }) {
    state.loadingSubmodule[submoduleType] = true;
    state.errorSubmodule[submoduleType] = null;
    state.dataSubmodule[submoduleType] = null;
    const pagination = state.paginationSubmodule[submoduleType];
    try {
      const queryParams = new URLSearchParams({
        page: String(pagination.page),
        limit: String(pagination.rowsPerPage),
      });
      if (pagination.sortBy) {
        queryParams.append('sort_by', pagination.sortBy);
      }
      if (pagination.descending) {
        queryParams.append(
          'sort_order',
          pagination.descending ? 'desc' : 'asc',
        );
      }
      const filterTerm = state.filterTermSubmodule[submoduleType];
      if (filterTerm && filterTerm.trim().length > 0) {
        queryParams.append('filter', filterTerm.trim());
      }
      const url = `${modulePath(moduleType, unit, year)}/${encodeURIComponent(
        submoduleType,
      )}?${queryParams.toString()}`;

      const response = await api.get(url).json();

      state.dataSubmodule[submoduleType] = response as Submodule;
      // update pagination state based on response
      state.paginationSubmodule[submoduleType] = {
        page: pagination.page,
        rowsNumber: (response as Submodule).summary.total_items,
        sortBy: pagination.sortBy, // SortBy in the API
        descending: pagination.descending, // sortOrder in the API
        rowsPerPage: pagination.rowsPerPage,
      };

      state.loadedSubmodules[submoduleType] = true;
    } catch (err: unknown) {
      console.error(
        `[ModuleStore] API Error for ${moduleType}/${submoduleType}:`,
        err,
      );
      if (err instanceof Error) {
        console.error(`[ModuleStore] Error message:`, err.message);
        state.errorSubmodule[submoduleType] = err.message ?? 'Unknown error';
        state.dataSubmodule[submoduleType] = null;
      } else {
        console.error(`[ModuleStore] Unknown error:`, err);
        state.errorSubmodule[submoduleType] = 'Unknown error';
        state.dataSubmodule[submoduleType] = null;
      }
    } finally {
      state.loadingSubmodule[submoduleType] = false;
    }
  }

  async function getSubmoduleTaxonomy(
    moduleType: Module,
    submoduleType: string,
    year: string,
  ) {
    state.loading = true;
    state.error = null;
    state.taxonomySubmodule[submoduleType] = null;
    try {
      const taxonomy = (await api
        .get(
          `taxonomies/module/${encodeURIComponent(moduleType)}/${encodeURIComponent(submoduleType)}?year=${encodeURIComponent(year)}`,
        )
        .json()) as TaxonomyNode;
      state.taxonomySubmodule[submoduleType] = taxonomy;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.error = err.message ?? 'Unknown error';
        state.taxonomySubmodule[submoduleType] = null;
      } else {
        state.error = 'Unknown error';
        state.taxonomySubmodule[submoduleType] = null;
      }
    } finally {
      state.loading = false;
    }
  }

  interface Option {
    label: string;
    value: string;
  }
  type FieldValue = string | number | boolean | null | Option;
  async function postItem(
    moduleType: Module,
    unitId: number,
    year: string | number,
    submoduleType: string,
    payload: Record<string, FieldValue>,
  ) {
    state.error = null;
    try {
      if (typeof year === 'number') {
        year = year.toString();
      }

      const path = `${modulePath(moduleType, unitId, year)}/${encodeURIComponent(submoduleType)}`;
      const normalized: Record<string, string | number | boolean | null> = {};

      Object.entries(payload).forEach(([key, raw]) => {
        let value: unknown = raw;
        if (
          value &&
          typeof value === 'object' &&
          'value' in (value as Option) &&
          typeof (value as Option).value === 'string'
        ) {
          value = (value as Option).value;
        }
        normalized[key] =
          value === undefined
            ? null
            : (value as string | number | boolean | null);
      });

      // Module-specific payload adjustments
      if (moduleType === MODULES.EquipmentElectricConsumption) {
        // Fallback category if not provided by the form // for equipment
        normalized.category = (normalized.class as string) || 'Uncategorized';
      }

      const isRoundTrip =
        moduleType === MODULES.ProfessionalTravel && !!normalized.is_round_trip;
      const body =
        moduleType === MODULES.ProfessionalTravel
          ? (() => {
              const rest = { ...normalized };
              delete rest.is_round_trip;
              return rest;
            })()
          : normalized;

      try {
        await api.post(path, { json: body }).json();
      } catch (error: unknown) {
        if (
          error &&
          typeof error === 'object' &&
          'response' in error &&
          error.response
        ) {
          const { detail } = await (error.response as Response).json();
          throw new Error(detail, { cause: error });
        }
        throw error;
      }

      if (isRoundTrip) {
        const returnBody = {
          ...body,
          origin_iata: normalized.destination_iata,
          destination_iata: normalized.origin_iata,
          origin_name: normalized.destination_name,
          destination_name: normalized.origin_name,
        };
        try {
          await api.post(path, { json: returnBody }).json();
        } catch (error: unknown) {
          if (
            error &&
            typeof error === 'object' &&
            'response' in error &&
            error.response
          ) {
            const { detail } = await (error.response as Response).json();
            throw new Error(detail, { cause: error });
          }
          throw error;
        }
      }

      // Refresh module totals (used by module page)
      await getModuleTotals(moduleType, unitId, year);

      // Refetch the affected submodule with current pagination/sort state
      await getSubmoduleData({
        moduleType,
        unit: unitId,
        year,
        submoduleType: submoduleType,
      });

      invalidateValidatedTotals();
      requestEmissionBreakdownRefresh();
      invalidateEmissionBreakdown();
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  async function patchItem(
    moduleType: Module,
    submoduleType: AllSubmoduleTypes,
    unit: number,
    year: string,
    itemId: number,
    payload: Record<string, FieldValue>,
  ) {
    state.error = null;
    try {
      const path = `${modulePath(moduleType, unit, year)}/${encodeURIComponent(submoduleType)}/${encodeURIComponent(
        String(itemId),
      )}`;

      // Normalize payload similar to postItem
      const normalized: Record<string, string | number | boolean | null> = {};

      Object.entries(payload).forEach(([key, raw]) => {
        let value: unknown = raw;
        if (
          value &&
          typeof value === 'object' &&
          'value' in (value as Option) &&
          typeof (value as Option).value === 'string'
        ) {
          value = (value as Option).value;
        }
        normalized[key] =
          value === undefined
            ? null
            : (value as string | number | boolean | null);
      });

      await api.patch(path, { json: normalized }).json();

      // Refresh module totals (used by module page)
      await getModuleTotals(moduleType, unit, year);

      await getSubmoduleData({
        submoduleType,
        moduleType,
        unit,
        year,
      });

      invalidateValidatedTotals();
      requestEmissionBreakdownRefresh();
      invalidateEmissionBreakdown();
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  async function deleteItem(
    moduleType: Module,
    submoduleType: AllSubmoduleTypes,
    unit: number,
    year: string,
    itemId: number,
  ) {
    state.error = null;
    try {
      // Find affected submodule BEFORE deleting (item won't be in data after deletion)
      const path = `${modulePath(moduleType, unit, year)}/${encodeURIComponent(submoduleType)}/${encodeURIComponent(
        String(itemId),
      )}`;
      await api.delete(path);

      // Refresh module totals
      await getModuleTotals(moduleType, unit, year);

      // Refetch the affected submodule with current pagination/sort state
      await getSubmoduleData({
        moduleType,
        submoduleType,
        unit,
        year,
      });

      invalidateValidatedTotals();
      requestEmissionBreakdownRefresh();
      invalidateEmissionBreakdown();
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  async function getTravelStatsByClass(unit: number, year: string) {
    state.loadingTravelStatsByClass = true;
    state.errorTravelStatsByClass = null;
    try {
      const path = `modules/${encodeURIComponent(unit)}/${encodeURIComponent(year)}/professional-travel/stats-by-class`;
      const data = await api.get(path).json<Array<Record<string, unknown>>>();
      state.travelStatsByClass = data;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.errorTravelStatsByClass = err.message ?? 'Unknown error';
        state.travelStatsByClass = [];
      } else {
        state.errorTravelStatsByClass = 'Unknown error';
        state.travelStatsByClass = [];
      }
    } finally {
      state.loadingTravelStatsByClass = false;
    }
  }

  async function getTravelEvolutionOverTime(unit: number) {
    state.loadingTravelEvolutionOverTime = true;
    state.errorTravelEvolutionOverTime = null;
    try {
      const path = `modules/${encodeURIComponent(unit)}/evolution-over-time`;
      const data = await api.get(path).json<Array<Record<string, unknown>>>();
      state.travelEvolutionOverTime = data;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.errorTravelEvolutionOverTime = err.message ?? 'Unknown error';
        state.travelEvolutionOverTime = [];
      } else {
        state.errorTravelEvolutionOverTime = 'Unknown error';
        state.travelEvolutionOverTime = [];
      }
    } finally {
      state.loadingTravelEvolutionOverTime = false;
    }
  }

  async function getTopClassBreakdown(
    unit: number,
    year: string,
    moduleId: string,
  ) {
    state.loadingTopClassBreakdown = true;
    state.errorTopClassBreakdown = null;
    try {
      const path = `modules/${encodeURIComponent(unit)}/${encodeURIComponent(year)}/${encodeURIComponent(moduleId)}/top-class-breakdown`;
      const data = await api.get(path).json<Array<Record<string, unknown>>>();
      state.topClassBreakdown = data;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.errorTopClassBreakdown = err.message ?? 'Unknown error';
        state.topClassBreakdown = [];
      } else {
        state.errorTopClassBreakdown = 'Unknown error';
        state.topClassBreakdown = [];
      }
    } finally {
      state.loadingTopClassBreakdown = false;
    }
  }

  // Track which carbon report the cached emission breakdown belongs to
  const emissionBreakdownCarbonReportId = ref<number | null>(null);
  const emissionBreakdownInFlightReportId = ref<number | null>(null);
  const emissionBreakdownInFlightToken = ref(0);
  const emissionBreakdownRefreshSequence = ref(0);
  const emissionBreakdownLastConsumedSequence = ref(0);
  let emissionBreakdownInFlight: Promise<void> | null = null;

  function requestEmissionBreakdownRefresh() {
    emissionBreakdownRefreshSequence.value += 1;
  }

  function consumeEmissionBreakdownRefreshRequest(sequence: number): boolean {
    if (sequence <= emissionBreakdownLastConsumedSequence.value) return false;
    emissionBreakdownLastConsumedSequence.value = sequence;
    return true;
  }

  function invalidateEmissionBreakdown() {
    emissionBreakdownCarbonReportId.value = null;
  }

  async function getEmissionBreakdown(
    carbonReportId: number,
    excludeModules: number[] = [],
  ) {
    if (emissionBreakdownCarbonReportId.value === carbonReportId) return;
    if (
      emissionBreakdownInFlight &&
      emissionBreakdownInFlightReportId.value === carbonReportId
    ) {
      await emissionBreakdownInFlight;
      return;
    }

    state.loadingEmissionBreakdown = true;
    state.errorEmissionBreakdown = null;
    emissionBreakdownInFlightReportId.value = carbonReportId;
    const currentRequestToken = ++emissionBreakdownInFlightToken.value;
    const currentRequest = (async () => {
      // Only the latest in-flight request is allowed to update state.
      const isLatestRequest = () =>
        emissionBreakdownInFlightToken.value === currentRequestToken &&
        emissionBreakdownInFlightReportId.value === carbonReportId;

      try {
        const params = new URLSearchParams();
        excludeModules.forEach((id) =>
          params.append('exclude_modules', String(id)),
        );
        const qs = params.toString() ? `?${params.toString()}` : '';
        const path = `modules-stats/${encodeURIComponent(carbonReportId)}/emission-breakdown${qs}`;
        const data = await api.get(path).json<EmissionBreakdownResponse>();
        if (!isLatestRequest()) {
          return;
        }
        state.emissionBreakdown = data;
        emissionBreakdownCarbonReportId.value = carbonReportId;
      } catch (err: unknown) {
        if (!isLatestRequest()) {
          return;
        }
        if (err instanceof Error) {
          state.errorEmissionBreakdown = err.message ?? 'Unknown error';
          state.emissionBreakdown = null;
        } else {
          state.errorEmissionBreakdown = 'Unknown error';
          state.emissionBreakdown = null;
        }
        emissionBreakdownCarbonReportId.value = null;
      }
    })();
    emissionBreakdownInFlight = currentRequest;

    try {
      await currentRequest;
    } finally {
      if (emissionBreakdownInFlightToken.value === currentRequestToken) {
        state.loadingEmissionBreakdown = false;
        emissionBreakdownInFlight = null;
        emissionBreakdownInFlightReportId.value = null;
      }
    }
  }

  // Track which carbon report the cached validated totals belong to
  const validatedTotalsCarbonReportId = ref<number | null>(null);

  function invalidateValidatedTotals() {
    validatedTotalsCarbonReportId.value = null;
  }

  async function getValidatedTotals(carbonReportId: number) {
    state.loadingValidatedTotals = true;
    state.errorValidatedTotals = null;
    try {
      const path = `modules-stats/${encodeURIComponent(carbonReportId)}/validated-totals`;
      const data = await api.get(path).json<ValidatedTotalsResponse>();
      state.validatedTotals = data;
      validatedTotalsCarbonReportId.value = carbonReportId;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.errorValidatedTotals = err.message ?? 'Unknown error';
        state.validatedTotals = null;
      } else {
        state.errorValidatedTotals = 'Unknown error';
        state.validatedTotals = null;
      }
      validatedTotalsCarbonReportId.value = null;
    } finally {
      state.loadingValidatedTotals = false;
    }
  }

  async function getYearlyValidatedEmissions(unitId: number) {
    state.loadingYearlyValidatedEmissions = true;
    state.errorYearlyValidatedEmissions = null;
    try {
      const path = `unit/${encodeURIComponent(unitId)}/yearly-validated-emissions`;
      const data = await api.get(path).json<YearlyValidatedEmission[]>();
      state.yearlyValidatedEmissions = data;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.errorYearlyValidatedEmissions = err.message ?? 'Unknown error';
        state.yearlyValidatedEmissions = [];
      } else {
        state.errorYearlyValidatedEmissions = 'Unknown error';
        state.yearlyValidatedEmissions = [];
      }
    } finally {
      state.loadingYearlyValidatedEmissions = false;
    }
  }

  return {
    initializeSubmoduleState,
    getModuleData,
    getModuleTotals,
    getModuleTaxonomy,
    getSubmoduleData,
    getSubmoduleTaxonomy,
    postItem,
    patchItem,
    deleteItem,
    getTravelStatsByClass,
    getTravelEvolutionOverTime,
    getTopClassBreakdown,
    getValidatedTotals,
    invalidateValidatedTotals,
    getYearlyValidatedEmissions,
    getEmissionBreakdown,
    invalidateEmissionBreakdown,
    requestEmissionBreakdownRefresh,
    consumeEmissionBreakdownRefreshRequest,
    emissionBreakdownRefreshSequence,
    validatedTotalsCarbonReportId,
    state,
  };
});
