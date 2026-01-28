import { MODULES } from './modules';
import type { Module } from './modules';

export interface ModuleCardBadge {
  label: string;
  color?: string;
  textColor?: string;
}

export interface ModuleCard {
  module: Module;
  badge?: ModuleCardBadge;
  value?: string;
  active: boolean;
}

export const MODULE_CARDS: ModuleCard[] = [
  {
    module: MODULES.MyLab,
    value: '5',
    active: true,
  },
  {
    module: MODULES.ProfessionalTravel,
    value: "8'250",
    active: false,
  },
  {
    module: MODULES.Infrastructure,
    value: "8'250",
    active: false,
  },
  {
    module: MODULES.EquipmentElectricConsumption,
    value: "8'250",
    active: false,
  },
  {
    module: MODULES.Purchase,
    value: "8'250",
    active: false,
  },
  {
    module: MODULES.InternalServices,
    value: "8'250",
    active: false,
  },
  {
    module: MODULES.ExternalCloudAndAI,
    value: "8'250",
    active: false,
  },
];

export type ModuleCardType = (typeof MODULE_CARDS)[number];
