import type { Module } from 'src/constant/modules';

export type { Module };

export const timelineItems = [
  {
    icon: 'o_diversity_2',
    link: 'headcount' as Module,
  },

  {
    icon: 'o_science',
    link: 'process-emissions' as Module,
  },
  {
    icon: 'o_apartment',
    link: 'buildings' as Module,
  },
  {
    icon: 'o_bolt',
    link: 'equipment' as Module,
  },
  {
    icon: 'o_filter_drama',
    link: 'external-cloud-and-ai' as Module,
  },
  {
    icon: 'o_flight',
    link: 'professional-travel' as Module,
  },

  {
    icon: 'o_sell',
    link: 'purchase' as Module,
  },

  {
    icon: 'o_apps',
    link: 'research-facilities' as Module,
  },
];

export type TimelineItem = (typeof timelineItems)[number];

/** Ordered list of modules for navigation (same order as timelineItems). */
export const MODULES_ORDER: Module[] = timelineItems.map((item) => item.link);
