import { MODULES } from './modules';
import type { Module } from './modules';

export interface ModuleCardBadge {
  label: string;
  color?: string;
  textColor?: string;
}

export interface ModuleCard {
  module: Module;
  active: boolean;
  badge?: ModuleCardBadge;
}

export const MODULE_CARDS: ModuleCard[] = [
  {
    module: MODULES.Headcount,
    active: true,
    badge: {
      label: 'New',
      color: 'primary',
      textColor: 'white',
    },
  },
  {
    module: MODULES.ProcessEmissions,
    active: true,
  },
  {
    module: MODULES.Buildings,
    active: true,
  },
  {
    module: MODULES.EquipmentElectricConsumption,
    active: true,
  },
  {
    module: MODULES.ExternalCloudAndAI,
    active: true,
  },
  {
    module: MODULES.Purchase,
    active: true,
  },
  {
    module: MODULES.ProfessionalTravel,
    active: true,
    badge: {
      label: 'New',
      color: 'primary',
      textColor: 'white',
    },
  },
  {
    module: MODULES.ResearchFacilities,
    active: true,
  },
];

export type ModuleCardType = (typeof MODULE_CARDS)[number];
