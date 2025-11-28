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
  id?: string;
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
  total_annual_consumption_kwh: number;
  total_kg_co2eq: number;
}

export interface ModuleResponse {
  module_type: string;
  unit: string;
  year: string;
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
