import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.ExternalCloud]: {
    en: 'External Cloud',
    fr: 'External Cloud',
  },
  [MODULES_DESCRIPTIONS.ExternalCloud]: {
    en: 'Measure cloud computing emissions from external service providers.',
    fr: 'Measure cloud computing emissions from external service providers.',
  },
} as const;
