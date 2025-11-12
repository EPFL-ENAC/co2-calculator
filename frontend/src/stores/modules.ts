import { defineStore } from 'pinia';
import { ModuleState, Modules } from '../types';
import { MODULES } from 'src/constant/modules';

// This ensures every module key has a ModuleState value
type ModuleStates = { [K in Modules]: ModuleState };

export const useTimelineStore = defineStore('timeline', {
  state: () => ({
    itemStates: {
      [MODULES.MyLab]: 'validated',
      [MODULES.ProfessionalTravel]: 'in-progress',
      [MODULES.Infrastructure]: 'default',
      [MODULES.EquipmentElectricConsumption]: 'default',
      [MODULES.Purchase]: 'default',
      [MODULES.InternalServices]: 'default',
      [MODULES.ExternalCloud]: 'default',
    } as ModuleStates,
  }),
  actions: {
    setState(id: Modules, state: ModuleState) {
      this.itemStates[id] = state;
    },
  },
});
