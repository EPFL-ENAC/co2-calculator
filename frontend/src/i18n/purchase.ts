import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.Purchase]: {
    en: 'Purchases',
    fr: 'Achats',
  },
  [MODULES_DESCRIPTIONS.Purchase]: {
    en: 'Input annual purchases to assess supply chain emissions footprint',
    fr: "Saisissez vos achats annuels afin d'évaluer l'empreinte de la chaîne d'approvisionnement",
  },
} as const;
