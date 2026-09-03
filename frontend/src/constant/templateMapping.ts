import {
  MODULES,
  SUBMODULE_BUILDINGS_TYPES,
  SUBMODULE_EQUIPMENT_TYPES,
  SUBMODULE_EXTERNAL_CLOUD_TYPES,
  SUBMODULE_HEADCOUNT_TYPES,
  SUBMODULE_PROFESSIONAL_TRAVEL_TYPES,
  SUBMODULE_PURCHASE_TYPES,
  SUBMODULE_RESEARCH_FACILITIES_TYPES,
} from '@/constant/modules';
import type { AllSubmoduleTypes, Module } from '@/constant/modules';

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
  [`${MODULES.Equipment}:${SUBMODULE_EQUIPMENT_TYPES.Scientific}`]:
    'equipment_scientific_template.csv',
  [`${MODULES.Equipment}:${SUBMODULE_EQUIPMENT_TYPES.IT}`]:
    'equipment_IT_template.csv',
  [`${MODULES.Equipment}:${SUBMODULE_EQUIPMENT_TYPES.Other}`]:
    'equipment_other_template.csv',

  [`${MODULES.Purchase}:${SUBMODULE_PURCHASE_TYPES.BioProductPurchases}`]:
    'purchases_biological_chemical_gaseous_template.csv',
  [`${MODULES.Purchase}:${SUBMODULE_PURCHASE_TYPES.ConsumablePurchases}`]:
    'purchases_consumables_template.csv',
  [`${MODULES.Purchase}:${SUBMODULE_PURCHASE_TYPES.ITEquipmentPurchases}`]:
    'purchases_itequipment_template.csv',
  [`${MODULES.Purchase}:${SUBMODULE_PURCHASE_TYPES.OtherPurchases}`]:
    'purchases_other_template.csv',
  [`${MODULES.Purchase}:${SUBMODULE_PURCHASE_TYPES.ScientificEquipmentPurchases}`]:
    'purchases_scientificequipment_template.csv',
  [`${MODULES.Purchase}:${SUBMODULE_PURCHASE_TYPES.ServicePurchases}`]:
    'purchases_services_template.csv',
  [`${MODULES.Purchase}:${SUBMODULE_PURCHASE_TYPES.VehiclePurchases}`]:
    'purchases_vehicles_template.csv',

  [`${MODULES.ExternalCloudAndAI}:${SUBMODULE_EXTERNAL_CLOUD_TYPES.external_clouds}`]:
    'external_clouds_template.csv',
  [`${MODULES.ExternalCloudAndAI}:${SUBMODULE_EXTERNAL_CLOUD_TYPES.external_ai}`]:
    'external_ai_template.csv',
  [`${MODULES.Purchase}:${SUBMODULE_PURCHASE_TYPES.PurchasesCentralized}`]:
    'purchases_centralized_template.csv',

  // Both tables show the download button since #2007, but these entries
  // were missing, so the click did nothing (reported on #2026).
  [`${MODULES.ResearchFacilities}:${SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities}`]:
    'researchfacilities_common_template.csv',
  [`${MODULES.ResearchFacilities}:${SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities}`]:
    'researchfacilities_animals_template.csv',
};

// Modules whose submodule determines the template — fall back to a default when no submodule matches
const MODULE_DEFAULTS: Partial<Record<Module, string>> = {
  [MODULES.Purchase]: 'purchases_common_template.csv',
  [MODULES.Equipment]: 'equipments_template.csv',
  [MODULES.ProcessEmissions]: 'processemissions_template.csv',
};

export function getTemplateFileName(
  moduleType: Module,
  submoduleType?: AllSubmoduleTypes,
): string | null {
  const key = submoduleType ? `${moduleType}:${submoduleType}` : moduleType;
  return TEMPLATE_MAP[key] ?? MODULE_DEFAULTS[moduleType];
}
