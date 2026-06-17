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
  [MODULES.Equipment]: 4,
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

/**
 * Visual representation of a module's validation status (icon, color, label),
 * derived from the backend ModuleStatus source of truth. Shared by the module
 * sidebar and total-result badge so the three states render consistently.
 */
export interface ModuleStatusDisplay {
  /** Quasar color name for the indicator; empty = no indicator (not started). */
  color: string;
  /** Quasar icon name; empty = no icon (not started). */
  icon: string;
  /** i18n key for the status label. */
  label: string;
}

export const MODULE_STATUS_DISPLAY: Record<ModuleState, ModuleStatusDisplay> = {
  [MODULE_STATES.Default]: {
    color: '',
    icon: '',
    label: 'module_status_not_started',
  },
  [MODULE_STATES.InProgress]: {
    color: 'warning',
    icon: 'o_pending',
    label: 'module_status_in_progress',
  },
  [MODULE_STATES.Validated]: {
    color: 'positive',
    icon: 'o_check_circle',
    label: 'module_status_validated',
  },
};
