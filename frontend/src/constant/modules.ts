export const MODULES = {
  MyLab: 'my-lab',
  ProfessionalTravel: 'professional-travel',
  Infrastructure: 'infrastructure',
  EquipmentElectricConsumption: 'equipment-electric-consumption',
  Purchase: 'purchase',
  InternalServices: 'internal-services',
  ExternalCloud: 'external-cloud',
} as const;

export const MODULES_DESCRIPTIONS = {
  MyLab: 'my-lab-description',
  ProfessionalTravel: 'professional-travel-description',
  Infrastructure: 'infrastructure-description',
  EquipmentElectricConsumption: 'equipment-electric-consumption-description',
  Purchase: 'purchase-description',
  InternalServices: 'internal-services-description',
  ExternalCloud: 'external-cloud-description',
} as const;

export type Module = (typeof MODULES)[keyof typeof MODULES];

export const SUBMODULE_EQUIPMENT_TYPES = {
  Scientific: 'scientific',
  IT: 'it',
  Other: 'other',
} as const;

export const enumSubmodule = {
  member: 1,
  student: 2,
  scientific: 9,
  it: 10,
  other: 11,
  trips: 20,
  building: 30,
  energy_mix: 100,
} as const;

export type EnumSubmoduleType = keyof typeof enumSubmodule;

export type EquipmentElectricConsumptionSubType =
  (typeof SUBMODULE_EQUIPMENT_TYPES)[keyof typeof SUBMODULE_EQUIPMENT_TYPES];

export const SUBMODULE_HEADCOUNT_TYPES = {
  Member: 'member',
  Student: 'student',
} as const;

// MyLab subtypes are the same as Headcount subtypes
export type HeadcountSubType =
  (typeof SUBMODULE_HEADCOUNT_TYPES)[keyof typeof SUBMODULE_HEADCOUNT_TYPES];

export const SUBMODULE_PURCHASE_TYPES = {
  Consumable: 'consumable',
  Durable: 'durable',
  Good: 'good',
} as const;

export type PurchaseSubType =
  (typeof SUBMODULE_PURCHASE_TYPES)[keyof typeof SUBMODULE_PURCHASE_TYPES];

type PurchaseProps = {
  moduleType: typeof MODULES.Purchase;
  submoduleType?: PurchaseSubType;
};

export const SUBMODULE_INFRASTRUCTURE_TYPES = {
  Building: 'building',
  Facility: 'facility',
} as const;

export type InfrastructureSubType =
  (typeof SUBMODULE_INFRASTRUCTURE_TYPES)[keyof typeof SUBMODULE_INFRASTRUCTURE_TYPES];

type InfrastructureProps = {
  moduleType: typeof MODULES.Infrastructure;
  submoduleType?: InfrastructureSubType;
};

type EquipmentElectricConsumptionProps = {
  moduleType: typeof MODULES.EquipmentElectricConsumption;
  submoduleType?: EquipmentElectricConsumptionSubType;
};

export type MyLabProps = {
  moduleType: typeof MODULES.MyLab;
  submoduleType?: HeadcountSubType;
};

export const SUBMODULE_PROFESSIONAL_TRAVEL_TYPES = {
  Conference: 'conference',
  Fieldwork: 'fieldwork',
  Training: 'training',
  Other: 'other',
} as const;

export type ProfessionalTravelSubType =
  (typeof SUBMODULE_PROFESSIONAL_TRAVEL_TYPES)[keyof typeof SUBMODULE_PROFESSIONAL_TRAVEL_TYPES];

type ProfessionalTravelProps = {
  moduleType: typeof MODULES.ProfessionalTravel;
  submoduleType?: ProfessionalTravelSubType;
};

export const SUBMODULE_INTERNAL_SERVICES_TYPES = {
  ITSupport: 'it-support',
  Maintenance: 'maintenance',
  Other: 'other',
} as const;

export type InternalServicesSubType =
  (typeof SUBMODULE_INTERNAL_SERVICES_TYPES)[keyof typeof SUBMODULE_INTERNAL_SERVICES_TYPES];

type InternalServicesProps = {
  moduleType: typeof MODULES.InternalServices;
  submoduleType?: InternalServicesSubType;
};

export const SUBMODULE_EXTERNAL_CLOUD_TYPES = {
  SaaS: 'saas',
  IaaS: 'iaas',
  PaaS: 'paas',
  Other: 'other',
} as const;

export type ExternalCloudSubType =
  (typeof SUBMODULE_EXTERNAL_CLOUD_TYPES)[keyof typeof SUBMODULE_EXTERNAL_CLOUD_TYPES];

type ExternalCloudProps = {
  moduleType: typeof MODULES.ExternalCloud;
  submoduleType?: ExternalCloudSubType;
};

export type AllSubmoduleTypes =
  | EquipmentElectricConsumptionSubType
  | HeadcountSubType
  | PurchaseSubType
  | InfrastructureSubType
  | ProfessionalTravelSubType
  | InternalServicesSubType
  | ExternalCloudSubType;

export type ConditionalSubmoduleProps =
  | EquipmentElectricConsumptionProps
  | MyLabProps
  | PurchaseProps
  | InfrastructureProps
  | ProfessionalTravelProps
  | InternalServicesProps
  | ExternalCloudProps;

export const MODULES_LIST: Module[] = Object.values(MODULES);

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
  act_usage?: number;
  pas_usage?: number;
  act_power?: number;
  pas_power?: number;
  kg_co2eq?: number;
  fte?: number;
  note?: string;
  display_name?: string;
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
  stats?: Record<string, number>;
  retrieved_at: string;
  submodules: Record<string, Submodule>;
  totals: Totals;
}

export function getBackendModuleName(frontendModule: Module): string {
  const moduleMap: Record<Module, string> = {
    [MODULES.MyLab]: 'my_lab',
    [MODULES.ProfessionalTravel]: 'professional_travel',
    [MODULES.Infrastructure]: 'infrastructure',
    [MODULES.EquipmentElectricConsumption]: 'equipment_electric_consumption',
    [MODULES.Purchase]: 'purchase',
    [MODULES.InternalServices]: 'internal_services',
    [MODULES.ExternalCloud]: 'external_cloud',
  };
  return moduleMap[frontendModule] || frontendModule;
}
