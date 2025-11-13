export const MODULES = {
  MyLab: 'my-lab',
  ProfessionalTravel: 'professional-travel',
  Infrastructure: 'infrastructure',
  EquipmentElectricConsumption: 'equipment-electric-consumption',
  Purchase: 'purchase',
  InternalServices: 'internal-services',
  ExternalCloud: 'external-cloud',
} as const;

export type Module = (typeof MODULES)[keyof typeof MODULES];

export const MODULES_LIST: Module[] = Object.values(MODULES);

export const MODULES_PATTERN = MODULES_LIST.join('|');
