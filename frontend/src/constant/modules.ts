// Define modules as a runtime object
export const MODULES = {
  MyLab: 'my-lab',
  ProfessionalTravel: 'professional-travel',
  Infrastructure: 'infrastructure',
  EquipmentElectricConsumption: 'equipment-electric-consumption',
  Purchase: 'purchase',
  InternalServices: 'internal-services',
  ExternalCloud: 'external-cloud',
} as const;

// Create type-safe union of values
export type Modules = (typeof MODULES)[keyof typeof MODULES];

// Array of modules (runtime, type-safe)
export const modulesList: Modules[] = Object.values(MODULES);

// Regex pattern
export const MODULE_PATTERN = modulesList.join('|');
