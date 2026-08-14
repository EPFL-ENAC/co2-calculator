import { MODULES, Module } from 'src/constant/modules';
import { MODULES_ORDER } from 'src/constant/timelineItems';
import {
  TRAVELER_OTHER_EXTERNAL,
  TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
  TRAVELER_OTHER_INTERNAL,
  TRAVELER_OTHER_INTERNAL_LABEL_KEY,
} from 'src/constant/module-config/traveler-options';

/**
 * How a module behaves inside the Simulator Plan (PRD #1555):
 * - 'manual'    (type 1) — planner-specific manual entry, no prefill
 * - 'prefilled' (type 2) — reference-year prefill + per-row "% of
 *   reference year" slider + Calculator-identical input form
 * - 'empty'     (type 3) — empty by default, Calculator-identical form
 *
 * Travel is 'empty' UI-wise but the backend plain-copies the reference
 * year's rows into the plan as ordinary editable entries (#2018,
 * PLANNER_PLAIN_COPY_MODULE_TYPES) — no reference columns or % slider.
 */
export type PlannerBehavior = 'manual' | 'prefilled' | 'empty';

export interface PlannerModuleConfig {
  module: Module;
  behavior: PlannerBehavior;
  /**
   * Traveler dropdown options replacing headcount names (the planner has no
   * per-person roster). Values land in `user_institutional_id`.
   */
  travelerOptions?: Array<{ value: string; labelKey: string }>;
}

/**
 * Simulator Plan behavior per module. Rendered in Calculator order
 * (MODULES_ORDER) — see PLANNER_MODULES below.
 */
export const PLANNER_MODULE_CONFIG: Partial<
  Record<Module, PlannerModuleConfig>
> = {
  [MODULES.Headcount]: {
    module: MODULES.Headcount,
    behavior: 'prefilled',
  },
  [MODULES.ProfessionalTravel]: {
    module: MODULES.ProfessionalTravel,
    behavior: 'empty',
    travelerOptions: [
      {
        value: TRAVELER_OTHER_INTERNAL,
        labelKey: TRAVELER_OTHER_INTERNAL_LABEL_KEY,
      },
      {
        value: TRAVELER_OTHER_EXTERNAL,
        labelKey: TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
      },
    ],
  },
  [MODULES.ProcessEmissions]: {
    module: MODULES.ProcessEmissions,
    behavior: 'prefilled',
  },
  [MODULES.Buildings]: {
    module: MODULES.Buildings,
    behavior: 'prefilled',
  },
  [MODULES.Equipment]: {
    module: MODULES.Equipment,
    behavior: 'prefilled',
  },
  [MODULES.Purchase]: {
    module: MODULES.Purchase,
    behavior: 'manual',
  },
  [MODULES.ResearchFacilities]: {
    module: MODULES.ResearchFacilities,
    behavior: 'prefilled',
  },
  [MODULES.ExternalCloudAndAI]: {
    module: MODULES.ExternalCloudAndAI,
    behavior: 'prefilled',
  },
};

/** Planner modules in Calculator order (the PRD keeps the same ordering). */
export const PLANNER_MODULES: PlannerModuleConfig[] = MODULES_ORDER.map(
  (module) => PLANNER_MODULE_CONFIG[module],
).filter((config): config is PlannerModuleConfig => config !== undefined);
