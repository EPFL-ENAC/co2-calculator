import { outlinedApartment, outlinedApps, outlinedBolt, outlinedDiversity2, outlinedFilterDrama, outlinedFlight, outlinedScience, outlinedSell } from '@quasar/extras/material-icons-outlined';
import type { Module } from '@/constant/modules';

export type { Module };

export const timelineItems = [
  {
    icon: outlinedDiversity2,
    link: 'headcount' as Module,
  },

  {
    icon: outlinedScience,
    link: 'process-emissions' as Module,
  },
  {
    icon: outlinedApartment,
    link: 'buildings' as Module,
  },
  {
    icon: outlinedBolt,
    link: 'equipment' as Module,
  },
  {
    icon: outlinedFilterDrama,
    link: 'external-cloud-and-ai' as Module,
  },
  {
    icon: outlinedFlight,
    link: 'professional-travel' as Module,
  },

  {
    icon: outlinedSell,
    link: 'purchase' as Module,
  },

  {
    icon: outlinedApps,
    link: 'research-facilities' as Module,
  },
];

export type TimelineItem = (typeof timelineItems)[number];

/** Ordered list of modules for navigation (same order as timelineItems). */
export const MODULES_ORDER: Module[] = timelineItems.map((item) => item.link);
