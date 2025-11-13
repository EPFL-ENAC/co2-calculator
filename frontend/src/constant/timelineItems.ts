import { MODULES } from 'src/constant/modules';

export const timelineItems = [
  {
    icon: 'o_diversity_2',
    link: MODULES.MyLab,
  },
  {
    icon: 'o_flight',
    link: MODULES.ProfessionalTravel,
  },
  {
    icon: 'o_apartment',
    link: MODULES.Infrastructure,
  },
  {
    icon: 'o_bolt',
    link: MODULES.EquipmentElectricConsumption,
  },
  {
    icon: 'o_sell',
    link: MODULES.Purchase,
  },
  {
    icon: 'o_apps',
    link: MODULES.InternalServices,
  },
  {
    icon: 'o_filter_drama',
    link: MODULES.ExternalCloud,
  },
];

export type TimelineItem = (typeof timelineItems)[number];
