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
    en: 'Review and complete your unit's purchases.',
    fr: "Vérifiez et complétez les données d'achats de votre unité.",
  },
  [`${MODULES.Purchase}-documentation-link`]: {
    en: 'https://epfl-enac.github.io/co2-calculator-user-doc/purchases/',
    fr: 'https://epfl-enac.github.io/co2-calculator-user-doc/fr/purchases/',
  },
  [`${MODULES.Purchase}-title-subtext`]: {
    en: "This module helps you estimate your unit’s purchasing carbon footprint item by item, based on procurement records from the invoicing system. By default, each item is analyzed by its specific category to apply the corresponding spend-based emission factor.

- Centralized purchases: For these categories, you can enter physical consumption metrics (quantities used). The system will automatically apply activity-based emission factors to calculate the corresponding carbon footprint.
  
- Credit card purchases: These expenses are not currently imported automatically. Please enter your unit’s credit card purchases to ensure your assessment is as accurate as possible.
  
- Internal store purchases: Purchases made at chemical stores (ISIC-CHSP) should not be entered here; they can be viewed directly in the EPFL research facilities module.",
    fr: "Ce module vous aide à estimer l'empreinte carbone liée aux achats de votre unité, article par article, à partir des données d'approvisionnement enregistrées dans le système de facturation.

Par défaut, chaque article est analysé selon sa typologie précise afin de lui attribuer le facteur d'émission monétaire correspondant.

- Achats centralisés : pour ces catégories, vous pouvez saisir des données d'usage (quantités consommées). Le système appliquera alors automatiquement des facteurs d'émission basés sur l'utilisation afin de calculer l'empreinte carbone correspondant.
    
- Achats par carte de crédit : ces dépenses ne remontant pas automatiquement actuellement. Veuillez saisir vos achats par la carte de crédit de votre unité afin d'obtenir un bilan aussi précis que possible.
    
- Achats en magasins internes : Les achats effectués aux magasins de chimie (ISIC-CHSP) ne doivent pas être saisis ici ; ils peuvent être consultés directement dans le module Infrastructures de recherche EPFL.",
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
    en: 'Conversion coefficient to kg',
    fr: 'Coefficient de conversion en kg',
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
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.PurchasesCentralized}`]: {
    en: 'Centralized purchase | Centralized purchases',
    fr: 'Achats centralisés | achats centralisés',
  },
  [`${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.PurchasesCentralized}-table-title`]:
    {
      en: 'Centralized purchases ({count})',
      fr: 'Achats centralisés ({count})',
    },
  [`${MODULES.Purchase}-${SUBMODULE_PURCHASE_TYPES.PurchasesCentralized}-form-title`]:
    {
      en: 'Add centralized purchase',
      fr: 'Ajoutez un achat centralisé',
    },
} as const;
