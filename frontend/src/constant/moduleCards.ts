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
    badge: {
      label: 'Validated',
      color: 'accent',
    },
    value: '5',

    active: true,
  },
  {
    module: MODULES.ProfessionalTravel,
    badge: {
      label: 'home_in_progress',
      color: 'grey-2',
      textColor: 'grey-6',
    },
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
    badge: {
      label: 'In Progress',
      color: 'grey-2',
      textColor: 'grey-6',
    },
    value: "8'250",
    active: false,
  },
  {
    module: MODULES.Purchase,
    badge: {
      label: 'In Progress',
      color: 'grey-2',
      textColor: 'grey-6',
    },
    value: "8'250",
    active: false,
  },
  {
    module: MODULES.InternalServices,
    badge: {
      label: 'In Progress',
      color: 'grey-2',
      textColor: 'grey-6',
    },
    value: "8'250",
    active: false,
  },
  {
    module: MODULES.ExternalCloud,
    badge: {
      label: 'In Progress',
      color: 'grey-2',
      textColor: 'grey-6',
    },
    value: "8'250",
    active: false,
  },
] as const;

export type ModuleCardType = (typeof MODULE_CARDS)[number];
