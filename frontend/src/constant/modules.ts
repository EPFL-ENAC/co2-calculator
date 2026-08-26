import { MODULES_ORDER } from '@/constant/timelineItems';
import type { DataEntryPolicies } from '@/utils/dataEntryPolicy';
import { DATA_ENTRY_TYPE_IDS } from '@/types/module-lookups.gen';

export const MODULES = {
  Headcount: 'headcount',
  ProfessionalTravel: 'professional-travel',
  ProcessEmissions: 'process-emissions',
  Buildings: 'buildings',
  Equipment: 'equipment',
  Purchase: 'purchase',
  ResearchFacilities: 'research-facilities',
  ExternalCloudAndAI: 'external-cloud-and-ai',
  // should be removed
  Commuting: 'commuting',
  Food: 'food',
  Waste: 'waste',
  EmbodiedEnergy: 'embodied-energy',
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
  PurchasesCentralized: 'purchases_centralized',
} as const;

export type PurchaseSubType =
  (typeof SUBMODULE_PURCHASE_TYPES)[keyof typeof SUBMODULE_PURCHASE_TYPES];

type PurchaseProps = {
  moduleType: typeof MODULES.Purchase;
  submoduleType?: AllSubmoduleTypes; // PurchaseSubType;
};

export const SUBMODULE_RESEARCH_FACILITIES_TYPES = {
  ResearchFacilities: 'research-facilities',
  AnimalFacilities: 'animal_facilities',
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

// Generated from backend/app/models/data_entry.py (DataEntryTypeEnum) — see
// frontend/src/types/module-lookups.gen.ts. Two keys are added on top: the
// hyphenated research-facilities alias, and energy_mix (frontend-only, not a
// submodule). Extra keys are safe — nothing iterates this object, every
// consumer does a keyed lookup.
export const enumSubmodule = {
  ...DATA_ENTRY_TYPE_IDS,
  [SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities]:
    DATA_ENTRY_TYPE_IDS.research_facilities,
  energy_mix: 100,
} as const;

export type EnumSubmoduleType = keyof typeof enumSubmodule;

export type EquipmentSubType =
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
  moduleType: typeof MODULES.Equipment;
  submoduleType?: AllSubmoduleTypes; // EquipmentSubType;
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
    | typeof MODULES.EmbodiedEnergy;
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
// Note: MODULES_LIST is now aligned with MODULES_ORDER from timelineItems
export const MODULES_LIST = MODULES_ORDER;

export const MODULES_THRESHOLD_TYPES = ['fixed', 'median', 'top'] as const;
export const MODULES_PATTERN = MODULES_LIST.join('|');

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
  /** #951: row provenance — see utils/dataEntryPolicy branchOf/isFieldEditable. */
  source?: number | null;
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
  /** #951: edit rights per row provenance. Null for submodules the policy
   * layer doesn't cover (planner, embodied energy) — see
   * utils/dataEntryPolicy. */
  data_entry_policies?: DataEntryPolicies | null;
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
  incomplete_new_equipment_count?: number;
}

// TODO refactor: delete this vibe coded code and use your brain
export function getBackendModuleName(frontendModule: Module): string {
  const moduleMap: Record<Module, string> = {
    [MODULES.Headcount]: 'headcount',
    [MODULES.ProfessionalTravel]: 'professional_travel',
    [MODULES.Buildings]: 'buildings',
    [MODULES.Equipment]: 'equipment',
    [MODULES.Purchase]: 'purchase',
    [MODULES.ResearchFacilities]: 'research_facilities',
    [MODULES.ExternalCloudAndAI]: 'external_cloud_and_ai',
    [MODULES.ProcessEmissions]: 'process_emissions',
    [MODULES.Commuting]: 'commuting',
    [MODULES.Food]: 'food',
    [MODULES.Waste]: 'waste',
    [MODULES.EmbodiedEnergy]: 'embodied_energy',
  };
  return moduleMap[frontendModule] || frontendModule;
}

export interface TaxonomyNode {
  name: string;
  label: string;
  translation_key?: string;
  /**
   * Display metadata whitelisted by the node's backend handler
   * (`taxonomy_meta_fields`, #2391) — e.g. `use_unit` for a research
   * facility. Absent for handlers declaring none; never an emission
   * coefficient.
   */
  meta?: Record<string, string | number | null>;
  children?: TaxonomyNode[];
}
