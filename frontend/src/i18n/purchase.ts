import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.Purchase]: {
    en: 'Purchases',
    fr: 'Purchases',
  },
  [MODULES_DESCRIPTIONS.Purchase]: {
    en: 'Input annual purchases to assess supply chain emissions footprint',
    fr: 'Enter annual purchases to assess the supply chain footprint',
  },
} as const;
