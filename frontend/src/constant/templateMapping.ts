import {
  MODULES,
  SUBMODULE_BUILDINGS_TYPES,
  SUBMODULE_EXTERNAL_CLOUD_TYPES,
  SUBMODULE_HEADCOUNT_TYPES,
  SUBMODULE_PROFESSIONAL_TRAVEL_TYPES,
  SUBMODULE_PURCHASE_TYPES,
} from 'src/constant/modules';
import type { AllSubmoduleTypes, Module } from 'src/constant/modules';

// Key format: "moduleType" or "moduleType:submoduleType"
const TEMPLATE_MAP: Record<string, string> = {
  [`${MODULES.Headcount}:${SUBMODULE_HEADCOUNT_TYPES.Member}`]:
    'headcount_template.csv',
  [`${MODULES.ProfessionalTravel}:${SUBMODULE_PROFESSIONAL_TRAVEL_TYPES.Plane}`]:
    'travel_planes_template.csv',
  [`${MODULES.ProfessionalTravel}:${SUBMODULE_PROFESSIONAL_TRAVEL_TYPES.Train}`]:
    'travel_trains_template.csv',
  [`${MODULES.Buildings}:${SUBMODULE_BUILDINGS_TYPES.Building}`]:
    'building_rooms_template.csv',
  [`${MODULES.Buildings}:${SUBMODULE_BUILDINGS_TYPES.EnergyCombustion}`]:
    'building_energycombustions_template.csv',
  [`${MODULES.ExternalCloudAndAI}:${SUBMODULE_EXTERNAL_CLOUD_TYPES.external_clouds}`]:
    'external_clouds_template.csv',
  [`${MODULES.ExternalCloudAndAI}:${SUBMODULE_EXTERNAL_CLOUD_TYPES.external_ai}`]:
    'external_ai_template.csv',
  [`${MODULES.Purchase}:${SUBMODULE_PURCHASE_TYPES.AdditionalPurchases}`]:
    'purchases_additional_template.csv',
};

// Modules whose submodule determines the template — fall back to a default when no submodule matches
const MODULE_DEFAULTS: Partial<Record<Module, string>> = {
  [MODULES.Purchase]: 'purchases_common_template.csv',
  [MODULES.EquipmentElectricConsumption]: 'equipments_template.csv',
  [MODULES.ProcessEmissions]: 'processemissions_template.csv',
};

export function getTemplateFileName(
  moduleType: Module,
  submoduleType?: AllSubmoduleTypes,
): string | null {
  const key = submoduleType ? `${moduleType}:${submoduleType}` : moduleType;
  return TEMPLATE_MAP[key] ?? MODULE_DEFAULTS[moduleType];
}
