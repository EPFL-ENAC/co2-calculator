import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.Purchase]: {
    en: 'Purchases',
    fr: 'Achats',
  },
  [MODULES_DESCRIPTIONS.Purchase]: {
    en: 'Input annual purchases to assess supply chain emissions footprint',
    fr: 'traduction française manquante',
  },
} as const;
