import { defineStore } from 'pinia';
import { computed, reactive, ref } from 'vue';
import { MODULES, Module } from 'src/constant/modules';
import { api } from 'src/api/http';
import { useWorkspaceStore } from 'src/stores/workspace';
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
} from 'src/constant/modules';
import { useRoute } from 'vue-router';
import {
  getModuleTotals as fetchModuleTotals,
  type ModuleTotalsResponse,
} from 'src/api/modules';

/**
 * API response for inventory module
 */
interface InventoryModuleResponse {
  id: number;
  inventory_id: number;
  module_type_id: number;
  status: number;
}

export const useTimelineStore = defineStore('timeline', () => {
  // Initialize all modules with default status
  const itemStates = reactive<ModuleStates>({
    [MODULES.MyLab]: MODULE_STATES.Default,
    [MODULES.ProfessionalTravel]: MODULE_STATES.Default,
    [MODULES.Infrastructure]: MODULE_STATES.Default,
    [MODULES.EquipmentElectricConsumption]: MODULE_STATES.Default,
    [MODULES.Purchase]: MODULE_STATES.Default,
    [MODULES.InternalServices]: MODULE_STATES.Default,
    [MODULES.ExternalCloud]: MODULE_STATES.Default,
  });

  const loading = ref(false);
  const error = ref<string | null>(null);
  const currentInventoryId = ref<number | null>(null);
  const $route = useRoute();
  const currentModuleType = computed(() => $route.params.module as Module);

  const currentInventoryModuleState = computed(() => {
    return itemStates[currentModuleType.value];
  });

  const currentInventoryModuleEdit = computed(() => {
    return (
      currentInventoryModuleState.value === MODULE_STATES.Default ||
      currentInventoryModuleState.value === MODULE_STATES.InProgress
    );
  });
  /**
   * Fetch module statuses from the API for a given inventory.
   * This should be called when an inventory is selected.
   */
  async function fetchModuleStates(inventoryId: number) {
    loading.value = true;
    error.value = null;
    currentInventoryId.value = inventoryId;

    try {
      const response = (await api
        .get(`inventories/${inventoryId}/modules/`)
        .json()) as InventoryModuleResponse[];

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
    if (!currentInventoryId.value) {
      error.value = 'No inventory selected';
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
          `inventories/${currentInventoryId.value}/modules/${moduleTypeId}/status`,
          {
            json: { status: state },
          },
        )
        .json();
      await fetchModuleStates(currentInventoryId.value);
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
   * Reset the store state (e.g., when changing inventory)
   */
  function reset() {
    currentInventoryId.value = null;
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
    currentInventoryId,
    fetchModuleStates,
    setState,
    reset,
    currentState: currentInventoryModuleState,
    canEdit: currentInventoryModuleEdit,
  };
});

export const useModuleStore = defineStore('modules', () => {
  const state = reactive<{
    loading: boolean;
    error: string | null;
    data: ModuleResponse | null;
    expandedSubmodules: Record<string, boolean>; // key: submodule ID
    loadingSubmodule: Record<string, boolean>; // key: submodule ID
    errorSubmodule: Record<string, string | null>; // key: submodule ID
    dataSubmodule: Record<string, Submodule | null>; // key: submodule ID
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
    moduleTotals: ModuleTotalsResponse | null;
    loadingModuleTotals: boolean;
    errorModuleTotals: string | null;
  }>({
    loading: false,
    error: null,
    data: null,
    filterTermSubmodule: reactive({}),
    expandedSubmodules: reactive({}),
    loadingSubmodule: reactive({}),
    errorSubmodule: reactive({}),
    dataSubmodule: reactive({}),
    paginationSubmodule: reactive({}),
    loadedSubmodules: reactive({}),
    travelStatsByClass: [],
    loadingTravelStatsByClass: false,
    errorTravelStatsByClass: null,
    travelEvolutionOverTime: [],
    loadingTravelEvolutionOverTime: false,
    errorTravelEvolutionOverTime: null,
    moduleTotals: null,
    loadingModuleTotals: false,
    errorModuleTotals: null,
  });
  function modulePath(moduleType: Module, unit: string, year: string) {
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

  async function getModuleData(moduleType: Module, unit: string, year: string) {
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
    unit: string,
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

  async function getSubmoduleData({
    moduleType,
    submoduleType,
    unit,
    year,
  }: {
    moduleType: Module;
    submoduleType: string;
    unit: string;
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

  interface Option {
    label: string;
    value: string;
  }
  type FieldValue = string | number | boolean | null | Option;
  async function postItem(
    moduleType: Module,
    unitId: string,
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
      } else if (moduleType === MODULES.ProfessionalTravel) {
        // Add unit_id for professional travel (required by backend)
        normalized.unit_id = unitId;
      }

      const body = normalized;
      try {
        await api.post(path, { json: body }).json();
      } catch (error: unknown) {
        if (
          error &&
          typeof error === 'object' &&
          'response' in error &&
          error.response &&
          typeof error.response === 'object' &&
          'json' in error.response &&
          typeof error.response.json === 'function'
        ) {
          const errorBody = await error.response.json();
          console.error('[ModuleStore] Backend error response:', errorBody);
        }
        throw error;
      }

      // Refresh module totals (used by module page)
      await getModuleTotals(moduleType, unitId, year);

      // Refresh aggregated module totals (used by home page)
      await getModuleTotalsAggregated(unitId, Number(year));

      // Refetch the affected submodule with current pagination/sort state
      await getSubmoduleData({
        moduleType,
        unit: unitId,
        year,
        submoduleType: submoduleType,
      });

      // Auto-refetch travel stats if this is professional travel module
      if (moduleType === MODULES.ProfessionalTravel) {
        await getTravelStatsByClass(unitId, String(year));
      }
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  async function patchItem(
    moduleType: Module,
    submoduleType: AllSubmoduleTypes,
    unit: string,
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

      // Module-specific payload adjustments
      if (moduleType === MODULES.ProfessionalTravel) {
        // Ensure number_of_trips is an integer if present and prevent negative values
        if (
          'number_of_trips' in normalized &&
          normalized.number_of_trips !== null
        ) {
          const tripsValue = normalized.number_of_trips;
          let parsed: number;
          if (typeof tripsValue === 'string') {
            parsed = parseInt(tripsValue, 10);
            if (isNaN(parsed)) {
              throw new Error('number_of_trips must be a valid integer');
            }
          } else if (typeof tripsValue === 'number') {
            parsed = Math.floor(tripsValue);
          } else {
            throw new Error('number_of_trips must be a number');
          }
          if (parsed < 1) {
            throw new Error('number_of_trips must be at least 1');
          }
          normalized.number_of_trips = parsed;
        }
      }

      await api.patch(path, { json: normalized }).json();

      // Refresh module totals (used by module page)
      await getModuleTotals(moduleType, unit, year);

      // Refresh aggregated module totals (used by home page)
      await getModuleTotalsAggregated(unit, Number(year));

      await getSubmoduleData({
        submoduleType,
        moduleType,
        unit,
        year,
      });

      // Auto-refetch travel stats if this is professional travel module
      if (moduleType === MODULES.ProfessionalTravel) {
        await getTravelStatsByClass(unit, year);
      }
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  async function deleteItem(
    moduleType: Module,
    submoduleType: AllSubmoduleTypes,
    unit: string,
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

      // Refresh aggregated module totals (used by home page)
      await getModuleTotalsAggregated(unit, Number(year));

      // Refetch the affected submodule with current pagination/sort state
      await getSubmoduleData({
        moduleType,
        submoduleType,
        unit,
        year,
      });

      // Auto-refetch travel stats if this is professional travel module
      if (moduleType === MODULES.ProfessionalTravel) {
        await getTravelStatsByClass(unit, year);
      }
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  async function getTravelStatsByClass(unit: string, year: string) {
    state.loadingTravelStatsByClass = true;
    state.errorTravelStatsByClass = null;
    try {
      const path = `professional-travel/${encodeURIComponent(unit)}/${encodeURIComponent(year)}/stats-by-class`;
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

  async function getTravelEvolutionOverTime(unit: string) {
    state.loadingTravelEvolutionOverTime = true;
    state.errorTravelEvolutionOverTime = null;
    try {
      const path = `professional-travel/${encodeURIComponent(unit)}/evolution-over-time`;
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

  // Track which unit/year the current totals are for
  const moduleTotalsUnitId = ref<string | null>(null);
  const moduleTotalsYear = ref<number | null>(null);

  /**
   * Fetch module totals (aggregated across equipment and professional-travel modules).
   *
   * @param unitId - Unit ID
   * @param year - Year for the data (must be a number)
   */
  async function getModuleTotalsAggregated(unitId: string, year: number) {
    state.loadingModuleTotals = true;
    state.errorModuleTotals = null;
    try {
      state.moduleTotals = await fetchModuleTotals(unitId, year);
      moduleTotalsUnitId.value = unitId;
      moduleTotalsYear.value = year;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.errorModuleTotals = err.message ?? 'Unknown error';
        state.moduleTotals = null;
      } else {
        state.errorModuleTotals = 'Unknown error';
        state.moduleTotals = null;
      }
      moduleTotalsUnitId.value = null;
      moduleTotalsYear.value = null;
    } finally {
      state.loadingModuleTotals = false;
    }
  }

  /**
   * Get module total for a specific module.
   *
   * @param module - Module name (e.g., "equipment-electric-consumption", "professional-travel")
   * @returns Module total in tCO2eq, or null if not available
   */
  function getModuleTotal(module: string): number | null {
    if (!state.moduleTotals) {
      return null;
    }
    return state.moduleTotals[module] ?? null;
  }

  const workspaceStore = useWorkspaceStore();
  const moduleTotals = computed(() => {
    const unitId = workspaceStore.selectedUnit?.id;
    const year = workspaceStore.selectedYear ?? new Date().getFullYear();

    if (
      unitId &&
      year &&
      (moduleTotalsUnitId.value !== unitId || moduleTotalsYear.value !== year)
    ) {
      getModuleTotalsAggregated(unitId, year);
    }
    return state.moduleTotals;
  });

  return {
    initializeSubmoduleState,
    getModuleData,
    getModuleTotals,
    getSubmoduleData,
    postItem,
    patchItem,
    deleteItem,
    getTravelStatsByClass,
    getTravelEvolutionOverTime,
    getModuleTotalsAggregated,
    getModuleTotal,
    moduleTotals,
    state,
  };
});
