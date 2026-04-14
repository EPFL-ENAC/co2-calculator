import { MODULES } from 'src/constant/modules';

export const timelineItems = [
  {
    icon: 'o_diversity_2',
    link: MODULES.Headcount,
  },

  {
    icon: 'o_science',
    link: MODULES.ProcessEmissions,
  },
  {
    icon: 'o_apartment',
    link: MODULES.Buildings,
  },
  {
    icon: 'o_bolt',
    link: MODULES.EquipmentElectricConsumption,
  },
  {
    icon: 'o_filter_drama',
    link: MODULES.ExternalCloudAndAI,
  },
  {
    icon: 'o_flight',
    link: MODULES.ProfessionalTravel,
  },

  {
    icon: 'o_sell',
    link: MODULES.Purchase,
  },

  {
    icon: 'o_apps',
    link: MODULES.ResearchFacilities,
  },
];

export type TimelineItem = (typeof timelineItems)[number];
