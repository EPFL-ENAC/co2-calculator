import { MODULES, SUBMODULE_PURCHASE_TYPES } from 'src/constant/modules';

export default {
  [MODULES.Purchase]: {
    en: 'Purchases',
    fr: 'Achats',
  },
  [`${MODULES.Purchase}-description`]: {
    en: 'Review annual purchase data and its carbon footprint.',
    fr: "Vérifiez vos données d'achats annuelles et leur empreintes carbones.",
  },
  [`${MODULES.Purchase}-title-subtext`]: {
    en: 'This module calculates the carbon footprint of your unit’s purchases on an item-by-item basis using imported data. Purchase entries can be reviewed and added by the user if necessary. Emissions are estimated using spend-based emission factors by default. For specific categories, such as liquid nitrogen, users may enter usage data to apply usage-based emission factors. If you have questions or need clarification regarding specific items, please contact XX.',
    fr: "Ce module calcule l'empreinte carbone des achats de votre unité, article par article, à partir des données importées. Vous pouvez consulter et ajouter des entrées d'achat selon vos besoins. Les émissions sont estimées par défaut à partir des dépenses. Pour certaines catégories (comme l'azote liquide), vous avez la possibilité de saisir des données d'usage afin d'utiliser des facteurs d'émission spécifiques. Si vous avez des questions ou besoin de clarification concernant vos achats, veuillez contacter XX.",
  },
  [`${MODULES.Purchase}-charts-title`]: {
    en: 'Charts',
    fr: 'Graphiques',
  },
  [`${MODULES.Purchase}.inputs.name`]: {
    en: 'Name',
    fr: 'Nom',
  },
  [`${MODULES.Purchase}.inputs.purchase_institutional_code`]: {
    en: 'Purchase Institutional Code',
    fr: "Code institutionnel d'achat",
  },
  [`${MODULES.Purchase}.inputs.supplier`]: {
    en: 'Supplier',
    fr: 'Fournisseur',
  },
  [`${MODULES.Purchase}.inputs.quantity`]: {
    en: 'Quantity',
    fr: 'Quantité',
  },
  [`${MODULES.Purchase}.inputs.total_spent_amount`]: {
    en: 'Total Spent Amount',
    fr: 'Montant total dépensé',
  },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ScientificEquipment}-table-title`]:
    {
      en: 'Scientific Equipments',
      fr: 'Équipements scientifiques',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ScientificEquipment}-form-title`]:
    {
      en: 'Add Scientific Equipment',
      fr: 'Ajouter un équipement scientifique',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ITEquipment}-table-title`]: {
    en: 'IT Equipments',
    fr: 'Équipements informatiques',
  },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ITEquipment}-form-title`]: {
    en: 'Add IT Equipment',
    fr: 'Ajouter un équipement informatique',
  },
} as const;
