import { MODULES, type Module } from './modules';
import type { ModuleCardBadge } from './moduleCards';

/**
 * Module status values matching backend ModuleStatus enum.
 * These are stored as integers in the database.
 */
export const MODULE_STATES = {
  Default: 0, // NOT_STARTED
  InProgress: 1, // IN_PROGRESS
  Validated: 2, // VALIDATED
} as const;

export type ModuleState = (typeof MODULE_STATES)[keyof typeof MODULE_STATES];
export type ModuleStates = { [K in Module]: ModuleState };

/**
 * Module type IDs matching backend module_types table.
 * Used for API calls to identify modules.
 */
export const MODULE_TYPE_IDS = {
  [MODULES.Headcount]: 1,
  [MODULES.ProfessionalTravel]: 2,
  [MODULES.Buildings]: 3,
  [MODULES.EquipmentElectricConsumption]: 4,
  [MODULES.Purchase]: 5,
  [MODULES.ResearchFacilities]: 6,
  [MODULES.ExternalCloudAndAI]: 7,
  [MODULES.ProcessEmissions]: 8,
  [MODULES.Commuting]: 9,
  [MODULES.Food]: 10,
  [MODULES.Waste]: 11,
  [MODULES.EmbodiedEnergy]: 12,
} as const;

export type ModuleTypeId =
  (typeof MODULE_TYPE_IDS)[keyof typeof MODULE_TYPE_IDS];

/**
 * Get the module type ID for a given module.
 */
export function getModuleTypeId(module: Module): ModuleTypeId {
  return MODULE_TYPE_IDS[module];
}

/**
 * Get the module key for a given module type ID.
 */
export function getModuleFromTypeId(typeId: number): Module | undefined {
  const entries = Object.entries(MODULE_TYPE_IDS) as [Module, number][];
  const found = entries.find(([, id]) => id === typeId);
  return found?.[0];
}

/**
 * Badge configuration for each module status.
 * Derives badge styling from the backend ModuleStatus source of truth.
 */
export const MODULE_STATUS_BADGES: Record<ModuleState, ModuleCardBadge | null> =
  {
    [MODULE_STATES.Default]: null, // NOT_STARTED - no badge shown
    [MODULE_STATES.InProgress]: {
      label: 'home_in_progress',
      color: 'grey-2',
      textColor: 'grey-6',
    },
    [MODULE_STATES.Validated]: {
      label: 'home_validated',
      color: 'accent',
    },
  };

/**
 * Get the badge configuration for a given module status.
 */
export function getBadgeForStatus(status: ModuleState): ModuleCardBadge | null {
  return MODULE_STATUS_BADGES[status] ?? null;
}
