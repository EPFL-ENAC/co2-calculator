import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.ExternalCloud]: {
    en: 'External Cloud',
    fr: 'Cloud externe',
  },
  [MODULES_DESCRIPTIONS.ExternalCloud]: {
    en: 'Measure cloud computing emissions from external service providers.',
    fr: "Mesurez les émissions liées à l'informatique en nuage auprès de fournisseurs externes.",
  },
} as const;
