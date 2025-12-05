import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { MODULES, Module } from 'src/constant/modules';
import { api } from 'src/api/http';
import {
  MODULE_STATES,
  ModuleState,
  ModuleStates,
} from 'src/constant/moduleStates';

import type { ModuleResponse } from 'src/constant/modules';

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
  }>({
    loading: false,
    error: null,
    data: null,
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

  async function createEquipment(
    moduleType: Module,
    unit: string,
    year: string,
    payload: Record<string, string | number | boolean | null>,
  ) {
    state.error = null;
    try {
      const path = `${modulePath(moduleType, unit, year)}/equipment`;
      // Backend validates body.unit_id equals path unit
      const body = { unit_id: unit, ...payload } as Record<string, unknown>;
      await api.post(path, { json: body }).json();
      await getModuleData(moduleType, unit, year);
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err; // let caller handle UI feedback
    }
  }

  async function updateEquipment(
    moduleType: Module,
    unit: string,
    year: string,
    equipmentId: number,
    payload: Record<string, string | number | boolean | null>,
  ) {
    state.error = null;
    try {
      const path = `${modulePath(moduleType, unit, year)}/equipment/${encodeURIComponent(
        String(equipmentId),
      )}`;
      await api.patch(path, { json: payload }).json();
      await getModuleData(moduleType, unit, year);
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  async function deleteEquipment(
    moduleType: Module,
    unit: string,
    year: string,
    equipmentId: number,
  ) {
    state.error = null;
    try {
      const path = `${modulePath(moduleType, unit, year)}/equipment/${encodeURIComponent(
        String(equipmentId),
      )}`;
      await api.delete(path);
      await getModuleData(moduleType, unit, year);
    } catch (err: unknown) {
      if (err instanceof Error) state.error = err.message ?? 'Unknown error';
      else state.error = 'Unknown error';
      throw err;
    }
  }

  return {
    getModuleData,
    createEquipment,
    updateEquipment,
    deleteEquipment,
    state,
  };
});
