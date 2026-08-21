import { MODULES, SUBMODULE_EXTERNAL_CLOUD_TYPES } from 'src/constant/modules';

export default {
  [MODULES.ExternalCloudAndAI]: {
    en: 'External clouds & AI',
    fr: 'Clouds externes & IA',
  },
  [`${MODULES.ExternalCloudAndAI}-description`]: {
    en: 'Enter your external cloud and AI usage.,
    fr: "Saisissez vos données d'utilisation de clouds externes et l'IA.",
  },
  [`${MODULES.ExternalCloudAndAI}-title-subtext`]: {
    en: 'This module helps you estimate the carbon footprint of external cloud and AI service usage.

To identify all usage across your unit, review licenses, subscriptions, and invoices paid over the past year. Be sure to include individual use of everyday tools, such as shared online storage or AI assistants (for writing, translation, or code generation,...).',
    fr: "Ce module vous aide à estimer l'empreinte carbone liée à l'utilisation de services cloud externes et d'intelligence artificielle.
  
Afin d'identifier l'ensemble des usages de votre unité, basez-vous sur les licences, abonnements ou factures réglés l'année écoulée. Veillez également à inclure les usages individuels des outils du quotidien, comme le stockage partagé en ligne ou les assistants IA (rédaction, traduction, génération de code,...).",
  },
  [`${MODULES.ExternalCloudAndAI}-documentation-link`]: {
    en: 'https://epfl-enac.github.io/co2-calculator-user-doc/external-cloud/',
    fr: 'https://epfl-enac.github.io/co2-calculator-user-doc/fr/external-cloud/',
  },
  // external-cloud-and-ai-external_clouds-form-title
  // Add an external cloud usage / Ajouter une utilisation de cloud externe
  [`${MODULES.ExternalCloudAndAI}-external_clouds-form-title`]: {
    en: 'Add an external cloud service usage',
    fr: 'Ajoutez une utilisation de service cloud externe',
  },

  // Add an external AI usage / Ajouter une utilisation d’IA externe
  [`${MODULES.ExternalCloudAndAI}-external_ai-form-title`]: {
    en: 'Add an external AI service usage',
    fr: "Ajoutez une utilisation de service d'IA externe",
  },

  // external-cloud-and-ai.cloud_services_table_title
  [`${MODULES.ExternalCloudAndAI}.cloud_services_table_title`]: {
    en: 'External cloud service ({count}) | External cloud services ({count})',
    fr: 'Service de cloud externe ({count}) | Services de clouds externes ({count})',
  },
  [`${MODULES.ExternalCloudAndAI}.cloud-services`]: {
    en: 'External cloud service | External cloud services',
    fr: 'Service de cloud externe | Services de clouds externes',
  },
  // external-cloud-and-ai.ai_usage_table_title
  [`${MODULES.ExternalCloudAndAI}.ai_usage_table_title`]: {
    en: 'External AI service ({count}) | External AI services ({count})',
    fr: "Service d'IA externe ({count}) | Services d'IAs externes ({count})",
  },
  [`${MODULES.ExternalCloudAndAI}.ai-services`]: {
    en: 'External AI service | External AI services',
    fr: "Service d'IA externe | Services d'IAs externes",
  },
  // CLOUD SUBMODULE
  [`${MODULES.ExternalCloudAndAI}.inputs.service_type`]: {
    en: 'Service Type',
    fr: 'Type de service',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.provider`]: {
    en: 'Provider',
    fr: 'Fournisseur',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.region`]: {
    en: 'Region',
    fr: 'Région',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.spent_amount`]: {
    en: 'Spending',
    fr: 'Dépenses',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.currency-hint`]: {
    en: 'Default is EUR.',
    fr: 'EUR par défaut.',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.currency`]: {
    en: 'Currency',
    fr: 'Devise',
  },
  // Co2eq is the same in both languages is using common key
  // AI SUBMODULE
  [`${MODULES.ExternalCloudAndAI}.inputs.usage_type`]: {
    en: 'Use',
    fr: 'Utilisation',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.requests_per_user_per_day`]: {
    en: 'Frequency (number of times per day)',
    fr: 'Fréquence (nombre de fois par jour)',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.requests_frequency.1_5`]: {
    en: '1–5 times/day',
    fr: '1–5 fois/jour',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.requests_frequency.5_20`]: {
    en: '5–20 times/day',
    fr: '5–20 fois/jour',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.requests_frequency.20_100`]: {
    en: '20–100 times/day',
    fr: '20–100 fois/jour',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.requests_frequency.gt_100`]: {
    en: '>100 times/day',
    fr: '>100 fois/jour',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.fte_count`]: {
    en: 'Number of users (FTE)',
    fr: "Nombre d'utilisateurs (EPT)",
  },

  [`${MODULES.ExternalCloudAndAI}-${SUBMODULE_EXTERNAL_CLOUD_TYPES.external_clouds}-form-disclaimer`]:
    {
      en: "The unit's external cloud management lead enters the data for the entire team",
      fr: "Le responsable de la gestion des clouds externes de l'unité remplit les données pour toute l'équipe",
    },
  [`${MODULES.ExternalCloudAndAI}-${SUBMODULE_EXTERNAL_CLOUD_TYPES.external_ai}-form-disclaimer`]:
    {
      en: 'Each member of the unit is responsible for recording their personal usage associated with their FTE',
      fr: "Chaque membre de l'unité est responsable de saisir son utilisation personnelle associé à son EPT",
    },
  [`${MODULES.ExternalCloudAndAI}-title-tooltip-subtext`]: {
    en: 'You can add data one at a time using the Add button below, or upload several entries at once using a file that follows the template.',
    fr: 'Vous pouvez ajouter les données une par une en utilisant le bouton « Ajouter » ci-dessous, ou importer plusieurs entrées à la fois via un fichier respectant le modèle fourni.',
  },
  storage: {
    en: 'Storage',
    fr: 'Stockage',
  },
  compute: {
    en: 'Compute',
    fr: 'Calcul',
  },
  virtualisation: {
    en: 'Virtualisation',
    fr: 'Virtualisation',
  },
} as const;
