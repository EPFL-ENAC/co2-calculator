import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { MODULES, Module } from 'src/constant/modules';
import { api } from 'src/api/http';
import {
  MODULE_STATES,
  ModuleState,
  ModuleStates,
} from 'src/constant/moduleStates';

import type { ModuleResponse, Submodule } from 'src/constant/modules';

export const useTimelineStore = defineStore('timeline', () => {
  const itemStates = reactive<ModuleStates>({
    [MODULES.MyLab]: MODULE_STATES.Validated,
    [MODULES.ProfessionalTravel]: MODULE_STATES.InProgress,
    [MODULES.Infrastructure]: MODULE_STATES.Default,
    [MODULES.EquipmentElectricConsumption]: MODULE_STATES.Default,
    [MODULES.Purchase]: MODULE_STATES.Default,
    [MODULES.InternalServices]: MODULE_STATES.Default,
    [MODULES.ExternalCloud]: MODULE_STATES.Default,
  });

  function setState(id: Module, state: ModuleState) {
    itemStates[id] = state;
  }

  return {
    itemStates,
    setState,
  };
});

export const useModuleStore = defineStore('modules', () => {
  const state = reactive<{
    loading: boolean;
    error: string | null;
    data: ModuleResponse | null;
    loadingSubmodule: Record<string, boolean>; // key: submodule ID
    errorSubmodule: Record<string, string | null>; // key: submodule ID
    dataSubmodule: Record<string, Submodule | null>; // key: submodule ID
    paginationSubmodule: Record<
      string,
      {
        page: number;
        limit: number;
        total: number;
        sortedBy?: string;
        sortOrder?: string;
      }
    >; // key: submodule ID
    loadedSubmodules: Record<string, boolean>; // key: submodule ID
  }>({
    loading: false,
    error: null,
    data: null,
    loadingSubmodule: {},
    errorSubmodule: {},
    dataSubmodule: {},
    paginationSubmodule: {},
    loadedSubmodules: {},
  });
  function modulePath(moduleType: Module, unit: string, year: string) {
    const moduleTypeEncoded = encodeURIComponent(moduleType);
    const unitEncoded = encodeURIComponent(unit);
    const yearEncoded = encodeURIComponent(year);
    // Backend expects /{unit_id}/{year}/{module_id}
    return `modules/${unitEncoded}/${yearEncoded}/${moduleTypeEncoded}`;
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

  async function getSubmoduleData(
    moduleType: Module,
    unit: string,
    year: string,
    submoduleId: string,
    page = 1,
    limit = 20,
    sortBy?: string,
    sortOrder?: string,
  ) {
    state.loadingSubmodule[submoduleId] = true;
    state.errorSubmodule[submoduleId] = null;
    state.dataSubmodule[submoduleId] = null;
    try {
      const queryParams = new URLSearchParams({
        page: String(page),
        limit: String(limit),
      });
      if (sortBy) {
        queryParams.append('sort_by', sortBy);
      }
      if (sortOrder) {
        queryParams.append('sort_order', sortOrder);
      }
      const response = await api
        .get(
          `${modulePath(moduleType, unit, year)}/sub_${encodeURIComponent(
            submoduleId,
          )}?${queryParams.toString()}`,
        )
        .json();
      state.dataSubmodule[submoduleId] = response as Submodule;
      state.paginationSubmodule[submoduleId] = {
        page,
        limit,
        total: (response as Submodule).summary.total_items,
        sortedBy: sortBy,
        sortOrder: sortOrder,
      };
      state.loadedSubmodules[submoduleId] = true;
    } catch (err: unknown) {
      if (err instanceof Error) {
        state.errorSubmodule[submoduleId] = err.message ?? 'Unknown error';
        state.dataSubmodule[submoduleId] = null;
      } else {
        state.errorSubmodule[submoduleId] = 'Unknown error';
        state.dataSubmodule[submoduleId] = null;
      }
    } finally {
      state.loadingSubmodule[submoduleId] = false;
    }
  }

  function findSubmoduleForEquipment(equipmentId: number): string | null {
    for (const [submoduleId, submodule] of Object.entries(
      state.dataSubmodule,
    )) {
      if (!submodule) continue;
      const found = submodule.items.find(
        (item) => item.id !== undefined && Number(item.id) === equipmentId,
      );
      if (found) {
        return submoduleId;
      }
    }
    return null;
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
    submoduleId: string,
    payload: Record<string, FieldValue>,
  ) {
    state.error = null;
    try {
      if (typeof year === 'number') {
        year = year.toString();
      }

      const path = `${modulePath(moduleType, unitId, year)}/equipment`;
      const normalized: Record<string, string | number | boolean | null> = {
        unit_id: unitId,
      };

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

      // Backend expects `submodule` (scientific|it|other), not `submodule_id`
      if (submoduleId) {
        const cleaned = submoduleId.startsWith('sub_')
          ? submoduleId.replace('sub_', '')
          : submoduleId;
        normalized.submodule = cleaned as string;
      }

      // Fallback category if not provided by the form
      if (!('category' in normalized) || !normalized.category) {
        normalized.category = (normalized.class as string) || 'Uncategorized';
      }

      const body = normalized;
      await api.post(path, { json: body }).json();

      // Normalize submoduleId for store key (remove 'sub_' prefix if present)
      const normalizedSubmoduleId = submoduleId.startsWith('sub_')
        ? submoduleId.replace('sub_', '')
        : submoduleId;

      // Refresh module totals
      await getModuleTotals(moduleType, unitId, year);

      // Refetch the affected submodule with current pagination/sort state
      const pagination = state.paginationSubmodule[normalizedSubmoduleId];
      if (pagination) {
        await getSubmoduleData(
          moduleType,
          unitId,
          year,
          normalizedSubmoduleId,
          pagination.page,
          pagination.limit,
          pagination.sortedBy,
          pagination.sortOrder,
        );
      }
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  async function patchItem(
    moduleType: Module,
    unit: string,
    year: string,
    equipmentId: number,
    payload: Record<string, FieldValue>,
  ) {
    state.error = null;
    try {
      const path = `${modulePath(moduleType, unit, year)}/equipment/${encodeURIComponent(
        String(equipmentId),
      )}`;
      await api.patch(path, { json: payload }).json();

      // Find affected submodule
      const affectedSubmoduleId = findSubmoduleForEquipment(equipmentId);

      // Refresh module totals
      await getModuleTotals(moduleType, unit, year);

      // Refetch the affected submodule with current pagination/sort state
      if (affectedSubmoduleId) {
        const pagination = state.paginationSubmodule[affectedSubmoduleId];
        if (pagination) {
          await getSubmoduleData(
            moduleType,
            unit,
            year,
            affectedSubmoduleId,
            pagination.page,
            pagination.limit,
            pagination.sortedBy,
            pagination.sortOrder,
          );
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  async function deleteItem(
    moduleType: Module,
    unit: string,
    year: string,
    equipmentId: number,
  ) {
    state.error = null;
    try {
      // Find affected submodule BEFORE deleting (item won't be in data after deletion)
      const affectedSubmoduleId = findSubmoduleForEquipment(equipmentId);

      const path = `${modulePath(moduleType, unit, year)}/equipment/${encodeURIComponent(
        String(equipmentId),
      )}`;
      await api.delete(path);

      // Refresh module totals
      await getModuleTotals(moduleType, unit, year);

      // Refetch the affected submodule with current pagination/sort state
      if (affectedSubmoduleId) {
        const pagination = state.paginationSubmodule[affectedSubmoduleId];
        if (pagination) {
          await getSubmoduleData(
            moduleType,
            unit,
            year,
            affectedSubmoduleId,
            pagination.page,
            pagination.limit,
            pagination.sortedBy,
            pagination.sortOrder,
          );
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  return {
    getModuleData,
    getModuleTotals,
    getSubmoduleData,
    postItem,
    patchItem,
    deleteItem,
    state,
  };
});
