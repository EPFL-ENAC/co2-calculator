import { MODULES, SUBMODULE_PURCHASE_TYPES } from 'src/constant/modules';

export default {
  [MODULES.Purchase]: {
    en: 'Purchases',
    fr: 'Achats',
  },
  [`${MODULES.Purchase}-common`]: {
    en: 'Common data and factors | Common data and factors',
    fr: 'Données et facteurs communs | Données et facteurs communs',
  },
  [`${MODULES.Purchase}-description`]: {
    en: 'Review annual purchase data and its carbon footprint.',
    fr: "Vérifiez vos données d'achats annuelles et leur empreinte carbone.",
  },
  [`${MODULES.Purchase}-title-subtext`]: {
    en: "This module calculates the carbon footprint of your unit’s purchases on an item-by-item basis by using procurement data registered in the EPFL's invoice system. You can review the entries and manually add any missing purchases. By default, emissions are estimated using financial spend-based emission factors. However, for specific centralized purchase categories where you can enter usage data, the system will automatically apply usage-based emission factors. Please note that purchases, such that made through internal shops or via units' credit cards, are not currently included in the automatic sync. We highly encourage you to manually fill in these expenses to receive a complete overview for your unit.",
    fr: "Ce module calcule l'empreinte carbone des achats de votre unité, article par article, en utilisant les données d'approvisionnement enregistrées dans le système EPFL de facturation. Vous pouvez vérifier les entrées et ajouter manuellement les achats manquants. Par défaut, les émissions sont estimées à l'aide de facteurs d'émission basés sur les dépenses financières. Cependant, pour certaines catégories d'achats centralisés où vous pouvez saisir des données d'utilisation, le système appliquera automatiquement des facteurs d'émission basés sur l'utilisation. Veuillez noter qu'actuellement les achats effectués auprès de magasins internes ou via les cartes de crédit des unités, ne remontent pas automatiquement. Nous vous encourageons vivement à renseigner manuellement ces dépenses afin d'obtenir une image de vos achats aussi précise que possible.",
  },
  [`${MODULES.Purchase}-charts-title`]: {
    en: 'Charts',
    fr: 'Graphiques',
  },
  [`${MODULES.Purchase}.inputs.name`]: {
    en: 'Item description',
    fr: 'Description de l’article',
  },
  [`${MODULES.Purchase}.inputs.purchase_institutional_code`]: {
    en: 'UNSPSC description',
    fr: 'Description UNSPSC',
  },
  [`${MODULES.Purchase}.inputs.purchase_institutional_code-hint`]: {
    en: '',
    fr: '',
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
    en: 'Total spent amount',
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
    en: 'Annual consumption',
    fr: 'Consommation annuelle',
  },
  [`${MODULES.Purchase}.inputs.unit`]: {
    en: 'Unit',
    fr: 'Unité',
  },
  [`${MODULES.Purchase}.inputs.coef_to_kg`]: {
    en: 'Conversion coefficient to kg CO₂-eq',
    fr: 'Coefficient de conversion en kg CO₂-eq',
  },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ScientificEquipmentPurchases}-table-title`]:
    {
      en: 'Scientific equipment ({count})',
      fr: 'Équipements scientifiques ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ScientificEquipmentPurchases}-form-title`]:
    {
      en: 'Add scientific equipment',
      fr: 'Ajoutez un équipement scientifique',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ITEquipmentPurchases}-table-title`]:
    {
      en: 'IT equipment ({count})',
      fr: 'Équipements informatiques ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ITEquipmentPurchases}-form-title`]:
    {
      en: 'Add IT equipment',
      fr: 'Ajoutez un équipement informatique',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ConsumablePurchases}-table-title`]:
    {
      en: 'Consumables & accessories ({count})',
      fr: 'Consommables et accessoires ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ConsumablePurchases}-form-title`]:
    {
      en: 'Add consumable',
      fr: 'Ajoutez un consommable',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.BioProductPurchases}-table-title`]:
    {
      en: 'Biological, chemical & gaseous products ({count})',
      fr: 'Produits biologiques chimiques et gazeux ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.BioProductPurchases}-form-title`]:
    {
      en: 'Add biological, chemical & gaseous product',
      fr: 'Ajoutez un produit biologique, chimique et gazeux',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ServicePurchases}-table-title`]:
    {
      en: 'Services ({count})',
      fr: 'Services ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.ServicePurchases}-form-title`]:
    {
      en: 'Add service',
      fr: 'Ajoutez un service',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.VehiclePurchases}-table-title`]:
    {
      en: 'Vehicles ({count})',
      fr: 'Véhicules ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.VehiclePurchases}-form-title`]:
    {
      en: 'Add vehicle',
      fr: 'Ajoutez un véhicule',
    },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.OtherPurchases}-table-title`]:
    {
      en: 'Other purchases ({count})',
      fr: 'Autres achats ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.OtherPurchases}-form-title`]:
    {
      en: 'Add other purchase',
      fr: 'Ajoutez un autre achat',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.AdditionalPurchases}`]: {
    en: 'Centralized purchase | Centralized purchases',
    fr: 'Achats centralisés | achats centralisés',
  },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.AdditionalPurchases}-table-title`]:
    {
      en: 'Centralized purchases ({count})',
      fr: 'Achats centralisés ({count})',
    },
} as const;
