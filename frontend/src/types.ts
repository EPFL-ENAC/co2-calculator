export type Language = 'en' | 'fr';

export type ModuleState = 'default' | 'in-progress' | 'validated';

export type Modules =
  | 'my-lab'
  | 'professional-travel'
  | 'infrastructure'
  | 'equipment-electric-consumption'
  | 'purchase'
  | 'internal-services'
  | 'external-cloud';

export type TimelineItem = {
  id: number;
  icon: string;
  link: Modules;
  label: string;
};
