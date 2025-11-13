export type Language = 'en' | 'fr';

// ModuleStates type
export type ModuleState = 'default' | 'in-progress' | 'validated';
export type ModuleStates = { [K in Modules]: ModuleState };

export type Modules =
  | 'my-lab'
  | 'professional-travel'
  | 'infrastructure'
  | 'equipment-electric-consumption'
  | 'purchase'
  | 'internal-services'
  | 'external-cloud';

export type TimelineItem = {
  icon: string;
  link: Modules;
};
