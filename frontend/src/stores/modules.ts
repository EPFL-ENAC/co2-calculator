import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { MODULES, Module } from 'src/constant/modules';
import { ModuleState, ModuleStates } from 'src/constant/moduleStates';

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

  function setState(id: Module, state: ModuleState) {
    itemStates[id] = state;
  }

  return {
    itemStates,
    setState,
  };
});
