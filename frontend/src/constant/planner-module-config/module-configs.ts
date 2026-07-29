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
 * - Travel's traveler dropdown offers categories instead of headcount names.
 *
 * Headcount and Purchases are NOT here — they render through
 * PlannerHeadcountRows (fixed SIUS-category grid) and PlannerPurchaseRows
 * (global budget XOR per-category grid), not data tables.
 */

function plannerTravelerField(categories: string[]): Partial<ModuleField> {
  return {
    type: 'select',
    optionLabelKey: 'planner_traveler_category.{value}',
    options: categories.map((value) => ({ value, label: value })),
  };
}

/** Clone a Calculator config with the planner adaptations applied. */
function withPlannerAdaptations(module: Module): ModuleConfig {
  const base = MODULES_CONFIG[module] as ModuleConfig;
  const travelerCategories =
    PLANNER_MODULE_CONFIG[module]?.travelerCategories ?? null;
  const submodules: Submodule[] = (base.submodules ?? []).map((sub) => ({
    ...sub,
    hasTableTopBar: false,
    moduleFields: (sub.moduleFields ?? []).map((field) =>
      travelerCategories && field.type === 'headcount-member-select'
        ? { ...field, ...plannerTravelerField(travelerCategories) }
        : field,
    ),
  }));
  return { ...base, submodules };
}

/** The ModuleConfig to render for a module inside the Simulator Plan. */
export function getPlannerModuleConfig(module: Module): ModuleConfig {
  return withPlannerAdaptations(module);
}
