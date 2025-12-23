import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.InternalServices]: {
    en: 'Internal Services',
    fr: 'Internal Services',
  },
  [MODULES_DESCRIPTIONS.InternalServices]: {
    en: 'Track usage of EPFL internal platforms and services (e.g., microscopy center, computing).',
    fr: 'Track the use of EPFL internal platforms and services.',
  },
} as const;
