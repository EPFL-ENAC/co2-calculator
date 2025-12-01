import { MODULES } from './modules';
import type { Module } from './modules';

export interface ModuleCardBadge {
  label: string;
  color?: string;
  textColor?: string;
}

export interface ModuleCard {
  module: Module;
  icon: string;
  badge?: ModuleCardBadge;
  value?: string;
  active: boolean;
}

export const MODULE_CARDS: ModuleCard[] = [
  {
    module: MODULES.MyLab,
    icon: 'o_diversity_2',
    badge: {
      label: 'Validated',
      color: 'accent',
    },
    value: "8'250",
    active: true,
  },
  {
    module: MODULES.ProfessionalTravel,
    icon: 'o_flight',
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
    icon: 'o_domain',
    value: "8'250",
    active: false,
  },
  {
    module: MODULES.EquipmentElectricConsumption,
    icon: 'o_bolt',
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
    icon: 'o_sell',
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
    icon: 'o_apps',
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
    icon: 'o_filter_drama',
    badge: {
      label: 'In Progress',
      color: 'grey-2',
      textColor: 'grey-6',
    },
    value: "8'250",
    active: false,
  },
] as const;

export const MODULE_ICONS = MODULE_CARDS.reduce(
  (acc, card) => {
    acc[card.module] = card.icon;
    return acc;
  },
  {} as Record<string, string>,
);

export type ModuleCardType = (typeof MODULE_CARDS)[number];
