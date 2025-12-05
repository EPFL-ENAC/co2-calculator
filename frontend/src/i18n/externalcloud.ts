import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.ExternalCloud]: {
    en: 'External Cloud',
    fr: 'External Cloud',
  },
  [MODULES_DESCRIPTIONS.ExternalCloud]: {
    en: 'Measure cloud computing emissions from external service providers.',
    fr: 'Mesurer les émissions liées au cloud computing provenant de fournisseurs de services externes.',
  },
} as const;
