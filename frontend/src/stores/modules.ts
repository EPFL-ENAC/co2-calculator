import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { MODULES, Module } from 'src/constant/modules';
import { api } from 'src/api/http';
import {
  MODULE_STATES,
  ModuleState,
  ModuleStates,
} from 'src/constant/moduleStates';

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
    data: object | null; // bad type
  }>({
    loading: false,
    error: null,
    data: null,
  });
  async function getModuleData(moduleType: string, unit: string, year: string) {
    state.loading = true;
    state.error = null;
    state.data = null;
    try {
      const moduleTypeEncoded = encodeURIComponent(moduleType);
      const unitEncoded = encodeURIComponent(unit);
      const yearEncoded = encodeURIComponent(year);
      state.data = (await api
        .get(`modules/${moduleTypeEncoded}/${unitEncoded}/${yearEncoded}`)
        .json()) as object; // bad type
    } catch (err: Error | unknown) {
      if (err instanceof Error) {
        state.error = err?.message ?? 'Unknown error';
        state.data = null;
      } else {
        state.error = 'Unknown error';
        state.data = null;
      }
    } finally {
      state.loading = false;
    }
  }

  return {
    getModuleData,
    state,
  };
});
