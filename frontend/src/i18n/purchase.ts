import { MODULES, SUBMODULE_PURCHASE_TYPES } from 'src/constant/modules';

export default {
  [MODULES.Purchase]: {
    en: 'Purchases',
    fr: 'Achats',
  },
  [`${MODULES.Purchase}-common`]: {
    en: 'Common Purchase | Common Purchases',
    fr: 'Achat Communs | Achats Communs',
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
    en: 'Item Description',
    fr: 'Description de l’article',
  },
  [`${MODULES.Purchase}.inputs.purchase_institutional_code`]: {
    en: 'UNSPSC Code',
    fr: 'Code UNSPSC',
  },
  [`${MODULES.Purchase}.inputs.purchase_institutional_code-hint`]: {
    en: 'To identify the corresponding UNSPSC Code, please consult the reference table.',
    fr: 'Pour identifier le code UNSPSC correspondant, veuillez consulter le tableau de référence.',
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
  [`${MODULES.Purchase}.inputs.currency`]: {
    en: 'Currency',
    fr: 'Devise',
  },
  [`${MODULES.Purchase}.inputs.currency-hint`]: {
    en: 'Default is CHF.',
    fr: 'CHF par défaut.',
  },
  [`${MODULES.Purchase}.inputs.annual_consumption`]: {
    en: 'Annual Consumption',
    fr: 'Consommation annuelle',
  },
  [`${MODULES.Purchase}.inputs.unit`]: {
    en: 'Unit',
    fr: 'Unité',
  },
  [`${MODULES.Purchase}.inputs.coef_to_kg`]: {
    en: 'Conversion Coefficient to kg CO₂-eq',
    fr: 'Coefficient de conversion en kg CO₂-eq',
  },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ScientificEquipmentPurchases}-table-title`]:
    {
      en: 'Scientific Equipments ({count})',
      fr: 'Équipements scientifiques ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ScientificEquipmentPurchases}-form-title`]:
    {
      en: 'Add Scientific Equipment',
      fr: 'Ajouter un équipement scientifique',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ScientificEquipmentPurchases}-table-title-info-tooltip`]:
    {
      en: 'For this category, EPFL-specific emission factors are used.',
      fr: 'Pour cette catégorie, les facteurs d’émission spécifiques à l’EPFL sont utilisés.',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ITEquipmentPurchases}-table-title`]:
    {
      en: 'IT Equipments ({count})',
      fr: 'Équipements informatiques ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ITEquipmentPurchases}-form-title`]:
    {
      en: 'Add IT Equipment',
      fr: 'Ajouter un équipement informatique',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ConsumablePurchases}-table-title`]:
    {
      en: 'Consumables & Accessories ({count})',
      fr: 'Consommables et accessoires ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ConsumablePurchases}-form-title`]:
    {
      en: 'Add Consumable',
      fr: 'Ajouter un consommable',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.BioProductPurchases}-table-title`]:
    {
      en: 'Biological, Chemical & Gaseous Products ({count})',
      fr: 'Produits biologiques chimiques et gazeux ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.BioProductPurchases}-form-title`]:
    {
      en: 'Add Biological/Chemical/Gaseous Product',
      fr: 'Ajouter un produit biologique/chimique/gazeux',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ServicePurchases}-table-title`]:
    {
      en: 'Services ({count})',
      fr: 'Services ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ServicePurchases}-form-title`]:
    {
      en: 'Add Service',
      fr: 'Ajouter un service',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.VehiclePurchases}-table-title`]:
    {
      en: 'Vehicles ({count})',
      fr: 'Véhicules ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.VehiclePurchases}-form-title`]:
    {
      en: 'Add Vehicle',
      fr: 'Ajouter un véhicule',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.OtherPurchases}-table-title`]:
    {
      en: 'Other Purchases ({count})',
      fr: 'Autres achats ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.OtherPurchases}-form-title`]:
    {
      en: 'Add Other Purchase',
      fr: 'Ajouter un autre achat',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.AdditionalPurchases}`]:
    {
      en: 'Additional Purchase | Additional Purchases',
      fr: 'Achat supplémentaire | Achats supplémentaires',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.AdditionalPurchases}-table-title`]:
    {
      en: 'Additional Purchases ({count})',
      fr: 'Achats supplémentaires ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.AdditionalPurchases}-table-title-info-tooltip`]:
    {
      en: 'Enter annual consumption values if your unit uses any of the items listed below.',
      fr: 'Saisissez les consommations annuelles si votre unité utilise les éléments listés ci-dessous.',
    },
} as const;
