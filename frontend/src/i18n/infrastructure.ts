import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.Infrastructure]: {
    en: 'Infrastructure',
    fr: 'Infrastructures',
  },
  [MODULES_DESCRIPTIONS.Infrastructure]: {
    en: "Define your lab's physical footprint across EPFL buildings and spaces.",
    fr: "Définissez l'empreinte physique de votre laboratoire dans les bâtiments et espaces de l'EPFL.",
  },
} as const;
