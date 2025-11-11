import { defineStore } from 'pinia';
import { ModuleState, Modules } from '../types';

// List of all modules as a value array
export const modulesList: Modules[] = [
  'my-lab',
  'professional-travel',
  'infrastructure',
  'equipment-electric-consumption',
  'purchased',
  'internal-services',
  'external-cloud',
];

// This ensures every module key has a ModuleState value
type ModuleStates = { [K in Modules]: ModuleState };

export const useTimelineStore = defineStore('timeline', {
  state: () => ({
    itemStates: {
      'my-lab': 'validated',
      'professional-travel': 'in-progress',
      infrastructure: 'default',
      'equipment-electric-consumption': 'default',
      purchased: 'default',
      'internal-services': 'default',
      'external-cloud': 'default',
    } as ModuleStates,
  }),
  actions: {
    setState(id: Modules, state: ModuleState) {
      this.itemStates[id] = state;
    },
  },
});
