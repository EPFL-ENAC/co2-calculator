import type { ModuleConfig, Submodule } from 'src/constant/moduleConfig';
import { MODULES, type Module } from 'src/constant/modules';
import {
  PLANNER_MODULES,
  type PlannerBehavior,
} from 'src/constant/planner-module-config';
import { getPlannerModuleConfig } from 'src/constant/planner-module-config/module-configs';

export interface PlannerPrintModule {
  type: Module;
  behavior: PlannerBehavior;
  config: ModuleConfig;
  submodules: Submodule[];
}

/**
 * The planner's data-table modules, in Calculator order, rendered with the same
 * configs the Simulator Plan page uses (planner Purchase, no CSV top bar,
 * traveler categories).
 *
 * Headcount is excluded: it is a fixed SIUS-category grid, not a data table —
 * the print report renders it through PlannerPrintHeadcountTable.
 */
export function getPlannerPrintModules(): PlannerPrintModule[] {
  return PLANNER_MODULES.filter((entry) => entry.module !== MODULES.Headcount)
    .map((entry) => {
      const config = getPlannerModuleConfig(entry.module);
      return {
        type: entry.module,
        behavior: entry.behavior,
        config,
        submodules: config.submodules ?? [],
      };
    })
    .filter((module) => module.submodules.length > 0);
}
