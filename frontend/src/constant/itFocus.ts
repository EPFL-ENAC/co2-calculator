import { MODULES, type Module } from './modules';

/** Parent modules whose validation gates IT focus UI and per-category bars. */
export const IT_FOCUS_SOURCE_MODULES: readonly Module[] = [
  MODULES.EquipmentElectricConsumption,
  MODULES.Purchase,
  MODULES.ExternalCloudAndAI,
  MODULES.ResearchFacilities,
];

/** API `category_key` → timeline module used for validation. */
export const IT_FOCUS_CATEGORY_TO_MODULE: Record<string, Module> = {
  equipment_it: MODULES.EquipmentElectricConsumption,
  purchases_it: MODULES.Purchase,
  external_cloud_and_ai: MODULES.ExternalCloudAndAI,
  research_facilities_it: MODULES.ResearchFacilities,
};
