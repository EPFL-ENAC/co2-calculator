import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.InternalServices]: {
    en: 'Internal Services',
    fr: 'Services Internes',
  },
  [MODULES_DESCRIPTIONS.InternalServices]: {
    en: 'Track usage of  internal platforms and services (e.g., microscopy center, computing)',
    fr: "Suivez l'utilisation des plateformes et services internes (p. ex., centre de microscopie, calcul)",
  },
} as const;
