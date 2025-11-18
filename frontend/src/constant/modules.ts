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
