import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { ModuleState, Modules, ModuleStates } from '../types';
import { MODULES } from 'src/constant/modules';

export const useTimelineStore = defineStore('timeline', () => {
  const itemStates = reactive<ModuleStates>({
    [MODULES.MyLab]: 'validated',
    [MODULES.ProfessionalTravel]: 'in-progress',
    [MODULES.Infrastructure]: 'default',
    [MODULES.EquipmentElectricConsumption]: 'default',
    [MODULES.Purchase]: 'default',
    [MODULES.InternalServices]: 'default',
    [MODULES.ExternalCloud]: 'default',
  });

  function setState(id: Modules, state: ModuleState) {
    itemStates[id] = state;
  }

  return {
    itemStates,
    setState,
  };
});
