import { TimelineItem } from 'src/types';
import { MODULES } from 'src/constant/modules';

export const timelineItems: TimelineItem[] = [
  {
    id: 1,
    icon: 'o_diversity_2',
    link: MODULES.MyLab,
  },
  {
    id: 2,
    icon: 'o_flight',
    link: MODULES.ProfessionalTravel,
  },
  {
    id: 3,
    icon: 'o_apartment',
    link: MODULES.Infrastructure,
  },
  {
    id: 4,
    icon: 'o_bolt',
    link: MODULES.EquipmentElectricConsumption,
  },
  {
    id: 5,
    icon: 'o_sell',
    link: MODULES.Purchase,
  },
  {
    id: 6,
    icon: 'o_apps',
    link: MODULES.InternalServices,
  },
  {
    id: 7,
    icon: 'o_filter_drama',
    link: MODULES.ExternalCloud,
  },
];
