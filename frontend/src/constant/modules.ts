export const MODULES = {
  Headcount: 'headcount',
  ProfessionalTravel: 'professional-travel',
  ProcessEmissions: 'process-emissions',
  Buildings: 'buildings',
  EquipmentElectricConsumption: 'equipment-electric-consumption',
  Purchase: 'purchase',
  ResearchFacilities: 'research-facilities',
  ExternalCloudAndAI: 'external-cloud-and-ai',
  // should be removed
  Commuting: 'commuting',
  Food: 'food',
  Waste: 'waste',
  GreyEnergy: 'grey-energy',
} as const;

export type BackendModule = keyof typeof MODULES;
export type ModulePermission = (typeof MODULES)[BackendModule];

export type Module = (typeof MODULES)[keyof typeof MODULES];

export const SUBMODULE_EQUIPMENT_TYPES = {
  Scientific: 'scientific',
  IT: 'it',
  Other: 'other',
} as const;

export const SUBMODULE_EXTERNAL_CLOUD_TYPES = {
  external_clouds: 'external_clouds',
  external_ai: 'external_ai',
} as const;

export type ExternalCloudSubType =
  (typeof SUBMODULE_EXTERNAL_CLOUD_TYPES)[keyof typeof SUBMODULE_EXTERNAL_CLOUD_TYPES];

type ExternalCloudProps = {
  moduleType: typeof MODULES.ExternalCloudAndAI;
  submoduleType?: AllSubmoduleTypes; // ExternalCloudSubType;
};

export const SUBMODULE_PURCHASE_TYPES = {
  ScientificEquipmentPurchases: 'scientific_equipment',
  ITEquipmentPurchases: 'it_equipment',
  ConsumablePurchases: 'consumable_accessories',
  BioProductPurchases: 'biological_chemical_gaseous_product',
  ServicePurchases: 'services',
  VehiclePurchases: 'vehicles',
  OtherPurchases: 'other_purchases',
  AdditionalPurchases: 'additional_purchases',
} as const;

export type PurchaseSubType =
  (typeof SUBMODULE_PURCHASE_TYPES)[keyof typeof SUBMODULE_PURCHASE_TYPES];

type PurchaseProps = {
  moduleType: typeof MODULES.Purchase;
  submoduleType?: AllSubmoduleTypes; // PurchaseSubType;
};

export const SUBMODULE_RESEARCH_FACILITIES_TYPES = {
  ResearchFacilities: 'research_facilities',
  AnimalFacilities: 'mice_and_fish_animal_facilities',
} as const;

export type ResearchFacilitiesSubType =
  (typeof SUBMODULE_RESEARCH_FACILITIES_TYPES)[keyof typeof SUBMODULE_RESEARCH_FACILITIES_TYPES];

type ResearchFacilitiesProps = {
  moduleType: typeof MODULES.ResearchFacilities;
  submoduleType?: AllSubmoduleTypes; // ResearchFacilitiesSubType;
};

export const SUBMODULE_PROCESSES_TYPES = {
  ProcessEmissions: 'process_emissions',
} as const;

export type ProcessesSubType =
  (typeof SUBMODULE_PROCESSES_TYPES)[keyof typeof SUBMODULE_PROCESSES_TYPES];

type ProcessesProps = {
  moduleType: typeof MODULES.ProcessEmissions;
  submoduleType?: AllSubmoduleTypes; // ProcessesSubType;
};

// beware came straight from backend enum, make sure to keep in sync if backend changes
// backend/app/models/data_entry.py
export const enumSubmodule = {
  member: 1,
  student: 2,
  // todo replace with equipment types
  [SUBMODULE_EQUIPMENT_TYPES.Scientific]: 10,
  [SUBMODULE_EQUIPMENT_TYPES.IT]: 11,
  [SUBMODULE_EQUIPMENT_TYPES.Other]: 12,
  // travel
  plane: 20,
  train: 21,
  // building room
  building: 30,
  energy_combustion: 31,
  // external cloud and ai
  [SUBMODULE_EXTERNAL_CLOUD_TYPES.external_clouds]: 40,
  [SUBMODULE_EXTERNAL_CLOUD_TYPES.external_ai]: 41,
  // process emissions
  process_emissions: 50,
  // purchase submodules
  [SUBMODULE_PURCHASE_TYPES.ScientificEquipmentPurchases]: 60,
  [SUBMODULE_PURCHASE_TYPES.ITEquipmentPurchases]: 61,
  [SUBMODULE_PURCHASE_TYPES.ConsumablePurchases]: 62,
  [SUBMODULE_PURCHASE_TYPES.BioProductPurchases]: 63,
  [SUBMODULE_PURCHASE_TYPES.ServicePurchases]: 64,
  [SUBMODULE_PURCHASE_TYPES.VehiclePurchases]: 65,
  [SUBMODULE_PURCHASE_TYPES.OtherPurchases]: 66,
  [SUBMODULE_PURCHASE_TYPES.AdditionalPurchases]: 67,

  // research facilities
  [SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities]: 70,
  [SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities]: 71,
  // not a module per se
  energy_mix: 100,
} as const;

export type EnumSubmoduleType = keyof typeof enumSubmodule;

export type EquipmentElectricConsumptionSubType =
  (typeof SUBMODULE_EQUIPMENT_TYPES)[keyof typeof SUBMODULE_EQUIPMENT_TYPES];

export const SUBMODULE_HEADCOUNT_TYPES = {
  Member: 'member',
  Student: 'student',
} as const;

// Headcount subtypes are the same as Headcount subtypes
export type HeadcountSubType =
  (typeof SUBMODULE_HEADCOUNT_TYPES)[keyof typeof SUBMODULE_HEADCOUNT_TYPES];

export const SUBMODULE_BUILDINGS_TYPES = {
  Building: 'building',
  EnergyCombustion: 'energy_combustion',
} as const;

export type BuildingsSubType =
  (typeof SUBMODULE_BUILDINGS_TYPES)[keyof typeof SUBMODULE_BUILDINGS_TYPES];

type BuildingsProps = {
  moduleType: typeof MODULES.Buildings;
  submoduleType?: BuildingsSubType;
};

type EquipmentElectricConsumptionProps = {
  moduleType: typeof MODULES.EquipmentElectricConsumption;
  submoduleType?: AllSubmoduleTypes; // EquipmentElectricConsumptionSubType;
};

export type HeadcountProps = {
  moduleType: typeof MODULES.Headcount;
  submoduleType?: AllSubmoduleTypes; // HeadcountSubType;
};

export const SUBMODULE_PROFESSIONAL_TRAVEL_TYPES = {
  Plane: 'plane',
  Train: 'train',
} as const;

export type ProfessionalTravelSubType =
  (typeof SUBMODULE_PROFESSIONAL_TRAVEL_TYPES)[keyof typeof SUBMODULE_PROFESSIONAL_TRAVEL_TYPES];

type ProfessionalTravelProps = {
  moduleType: typeof MODULES.ProfessionalTravel;
  submoduleType?: AllSubmoduleTypes; // ProfessionalTravelSubType;
};

export type AllSubmoduleTypes = keyof typeof enumSubmodule;

type ChartOnlyProps = {
  moduleType:
    | typeof MODULES.Commuting
    | typeof MODULES.Food
    | typeof MODULES.Waste
    | typeof MODULES.GreyEnergy;
  submoduleType?: AllSubmoduleTypes;
};

export type ConditionalSubmoduleProps =
  | EquipmentElectricConsumptionProps
  | HeadcountProps
  | PurchaseProps
  | BuildingsProps
  | ProfessionalTravelProps
  | ResearchFacilitiesProps
  | ExternalCloudProps
  | ProcessesProps
  | ChartOnlyProps;

// Exclude the 4 modules that should be removed
// TODO: refactor the codebase to remove these 4 modules and then remove this exclusion
export const MODULES_LIST: Module[] = Object.values(MODULES).slice(0, -4);

export const MODULES_PATTERN = MODULES_LIST.join('|');

export const MODULES_THRESHOLD_TYPES = ['fixed', 'median', 'top'] as const;

export type ThresholdType = (typeof MODULES_THRESHOLD_TYPES)[number];

export interface Threshold {
  type: ThresholdType;
  value?: number;
}

export interface ModuleThreshold {
  module: Module;
  threshold: Threshold;
}

// MODULE RESPONSE TYPES
export interface ModuleItem {
  name: string;
  class?: string;
  sub_class?: string;
  active_usage_hours_per_week?: number;
  standby_usage_hours_per_week?: number;
  act_power?: number;
  pas_power?: number;
  kg_co2eq?: number;
  fte?: number;
  note?: string;
  position?: string;
  status?: string;
  is_new?: boolean;
  id?: number;
}

export interface Submodule {
  id: string;
  name: string;
  count?: number;
  items: ModuleItem[];
  summary: {
    total_items: number;
    annual_consumption_kwh: number;
    total_kg_co2eq: number;
  };
}

export interface Totals {
  total_submodules: number;
  total_items: number;
  total_annual_consumption_kwh?: number;
  total_kg_co2eq?: number;
  total_tonnes_co2eq?: number;
  total_annual_fte?: number;
}

export interface ModuleResponse {
  module_type: string;
  unit: number;
  year: string;
  data_entry_types_total_items: Record<number, number>;
  carbon_report_module_id: number;
  stats?: Record<string, number>;
  retrieved_at: string;
  submodules: Record<string, Submodule>;
  totals: Totals;
}

// TODO refactor: delete this vibe coded code and use your brain
export function getBackendModuleName(frontendModule: Module): string {
  const moduleMap: Record<Module, string> = {
    [MODULES.Headcount]: 'headcount',
    [MODULES.ProfessionalTravel]: 'professional_travel',
    [MODULES.Buildings]: 'buildings',
    [MODULES.EquipmentElectricConsumption]: 'equipment_electric_consumption',
    [MODULES.Purchase]: 'purchase',
    [MODULES.ResearchFacilities]: 'research_facilities',
    [MODULES.ExternalCloudAndAI]: 'external_cloud_and_ai',
    [MODULES.ProcessEmissions]: 'process_emissions',
    [MODULES.Commuting]: 'commuting',
    [MODULES.Food]: 'food',
    [MODULES.Waste]: 'waste',
    [MODULES.GreyEnergy]: 'grey_energy',
  };
  return moduleMap[frontendModule] || frontendModule;
}

export interface TaxonomyNode {
  name: string;
  label: string;
  children?: TaxonomyNode[];
}
