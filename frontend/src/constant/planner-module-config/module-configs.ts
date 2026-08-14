import type {
  ModuleConfig,
  ModuleField,
  Submodule,
} from 'src/constant/moduleConfig';
import type { Module } from 'src/constant/modules';
import { MODULES_CONFIG } from 'src/constant/module-config';
import { PLANNER_MODULE_CONFIG } from 'src/constant/planner-module-config';

/**
 * ModuleConfig objects rendered inside the Simulator Plan by
 * ModuleTableSection.
 *
 * Every module here reuses the Calculator config with two planner
 * adaptations applied by `withPlannerAdaptations`:
 * - no CSV top bar (bulk ingest pipelines are unit/year-scoped and would
 *   bypass the plan's report addressing)
 * - Travel's traveler dropdown offers the "Other traveler" options instead of
 *   headcount names, except for own-scoped users, whose traveler is pinned to
 *   themselves so the rows they create stay inside the own-rows read filter.
 *
 * Headcount and Purchases are NOT here — they render through
 * PlannerHeadcountRows (fixed SIUS-category grid) and PlannerPurchaseRows
 * (global budget XOR per-category grid), not data tables.
 */

export interface PlannerSelfTraveler {
  institutional_id: string;
  name: string;
}

function plannerTravelerField(
  options: Array<{ value: string; labelKey: string }>,
): Partial<ModuleField> {
  return {
    type: 'select',
    options: options.map(({ value, labelKey }) => ({
      value,
      label: labelKey,
    })),
  };
}

function selfTravelerField(self: PlannerSelfTraveler): Partial<ModuleField> {
  return {
    type: 'select',
    options: [{ value: self.institutional_id, label: self.name }],
    default: self.institutional_id,
  };
}

/** Clone a Calculator config with the planner adaptations applied. */
function withPlannerAdaptations(
  module: Module,
  self: PlannerSelfTraveler | null,
): ModuleConfig {
  const base = MODULES_CONFIG[module] as ModuleConfig;
  const travelerOptions =
    PLANNER_MODULE_CONFIG[module]?.travelerOptions ?? null;
  const submodules: Submodule[] = (base.submodules ?? []).map((sub) => ({
    ...sub,
    hasTableTopBar: false,
    moduleFields: (sub.moduleFields ?? []).map((field) =>
      travelerOptions && field.type === 'headcount-member-select'
        ? {
            ...field,
            ...(self
              ? selfTravelerField(self)
              : plannerTravelerField(travelerOptions)),
          }
        : field,
    ),
  }));
  return { ...base, submodules };
}

/** The ModuleConfig to render for a module inside the Simulator Plan. */
export function getPlannerModuleConfig(
  module: Module,
  self: PlannerSelfTraveler | null = null,
): ModuleConfig {
  return withPlannerAdaptations(module, self);
}
