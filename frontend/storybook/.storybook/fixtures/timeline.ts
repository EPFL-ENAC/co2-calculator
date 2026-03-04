import { MODULES } from 'src/constant/modules';
import { MODULE_STATES } from 'src/constant/moduleStates';
import type { ModuleStates } from 'src/constant/moduleStates';

/**
 * Timeline fixtures for Storybook stories.
 * Provides reusable timeline state configurations for different scenarios.
 */

/**
 * All modules in default state (not started).
 */
export const allDefault: Partial<ModuleStates> = {
  [MODULES.Headcount]: MODULE_STATES.Default,
  [MODULES.ProfessionalTravel]: MODULE_STATES.Default,
  [MODULES.Infrastructure]: MODULE_STATES.Default,
  [MODULES.EquipmentElectricConsumption]: MODULE_STATES.Default,
  [MODULES.Purchase]: MODULE_STATES.Default,
  [MODULES.InternalServices]: MODULE_STATES.Default,
  [MODULES.ExternalCloudAndAI]: MODULE_STATES.Default,
};

/**
 * Mixed states showing typical progression through modules.
 * First two validated, one in progress, rest default.
 */
export const mixedStates: Partial<ModuleStates> = {
  [MODULES.Headcount]: MODULE_STATES.Validated,
  [MODULES.ProfessionalTravel]: MODULE_STATES.Validated,
  [MODULES.Infrastructure]: MODULE_STATES.InProgress,
  [MODULES.EquipmentElectricConsumption]: MODULE_STATES.Default,
  [MODULES.Purchase]: MODULE_STATES.Default,
  [MODULES.InternalServices]: MODULE_STATES.Default,
  [MODULES.ExternalCloudAndAI]: MODULE_STATES.Default,
};

/**
 * Early stage: first module in progress, rest default.
 */
export const earlyStage: Partial<ModuleStates> = {
  [MODULES.Headcount]: MODULE_STATES.InProgress,
  [MODULES.ProfessionalTravel]: MODULE_STATES.Default,
  [MODULES.Infrastructure]: MODULE_STATES.Default,
  [MODULES.EquipmentElectricConsumption]: MODULE_STATES.Default,
  [MODULES.Purchase]: MODULE_STATES.Default,
  [MODULES.InternalServices]: MODULE_STATES.Default,
  [MODULES.ExternalCloudAndAI]: MODULE_STATES.Default,
};

/**
 * Mid stage: half validated, one in progress, rest default.
 */
export const midStage: Partial<ModuleStates> = {
  [MODULES.Headcount]: MODULE_STATES.Validated,
  [MODULES.ProfessionalTravel]: MODULE_STATES.Validated,
  [MODULES.Infrastructure]: MODULE_STATES.Validated,
  [MODULES.EquipmentElectricConsumption]: MODULE_STATES.InProgress,
  [MODULES.Purchase]: MODULE_STATES.Default,
  [MODULES.InternalServices]: MODULE_STATES.Default,
  [MODULES.ExternalCloudAndAI]: MODULE_STATES.Default,
};

/**
 * Late stage: most validated, last one in progress.
 */
export const lateStage: Partial<ModuleStates> = {
  [MODULES.Headcount]: MODULE_STATES.Validated,
  [MODULES.ProfessionalTravel]: MODULE_STATES.Validated,
  [MODULES.Infrastructure]: MODULE_STATES.Validated,
  [MODULES.EquipmentElectricConsumption]: MODULE_STATES.Validated,
  [MODULES.Purchase]: MODULE_STATES.Validated,
  [MODULES.InternalServices]: MODULE_STATES.Validated,
  [MODULES.ExternalCloudAndAI]: MODULE_STATES.InProgress,
};

/**
 * All modules in progress (unusual but possible state).
 */
export const allInProgress: Partial<ModuleStates> = {
  [MODULES.Headcount]: MODULE_STATES.InProgress,
  [MODULES.ProfessionalTravel]: MODULE_STATES.InProgress,
  [MODULES.Infrastructure]: MODULE_STATES.InProgress,
  [MODULES.EquipmentElectricConsumption]: MODULE_STATES.InProgress,
  [MODULES.Purchase]: MODULE_STATES.InProgress,
  [MODULES.InternalServices]: MODULE_STATES.InProgress,
  [MODULES.ExternalCloudAndAI]: MODULE_STATES.InProgress,
};
