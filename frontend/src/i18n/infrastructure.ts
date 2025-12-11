import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.Infrastructure]: {
    en: 'Infrastructure',
    fr: 'Infrastructure',
  },
  [MODULES_DESCRIPTIONS.Infrastructure]: {
    en: "Define your lab's physical footprint across EPFL buildings and spaces.",
    fr: "Bâtiments etc",
  },
} as const;
