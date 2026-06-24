import { MODULES, SUBMODULE_EXTERNAL_CLOUD_TYPES } from 'src/constant/modules';

export default {
  [MODULES.ExternalCloudAndAI]: {
    en: 'External clouds & AI',
    fr: 'Clouds externes & IA',
  },
  [`${MODULES.ExternalCloudAndAI}-description`]: {
    en: 'Enter your external clouds usage data to estimate the carbon footprint.',
    fr: "Saisissez vos données relatives à l'utilisation de clouds externes pour estimer leur empreinte carbone.",
  },
  [`${MODULES.ExternalCloudAndAI}-title-subtext`]: {
    en: 'This module calculates the carbon footprint associated with the use of external cloud services and AI. Some cells may or may not be editable depending on the type of service selected. For external cloud services, it is necessary to enter the provider name, used type of service (compute or storage), spending and associated currency. For AI services, it is necessary to enter the provider name, type of use (text, code or image generation), number of users and frequency of use. For more information: [external clouds & IA](https://epfl-enac.github.io/co2-calculator-user-doc/building/)',
    fr: "Ce module calcule l'empreinte carbone liée à l'utilisation de services de clouds externes et d'intelligence artificielle. Certaines cellules seront ou non éditables en fonction du type de service sélectionné. Pour les services de clouds externes, il est nécessaire de saisir le nom du fournisseur, le type de service utilisé (calcul ou stockage), le montant dépensé et la devise associée. Pour les services d'IAs, il faut fournir le nom du fournisseur, le type d'utilisation (génération de texte, de code ou d'image), le nombre d'utilisateurs et la fréquence d'utilisation. Pour plus d'information : [clouds externes et IA](https://epfl-enac.github.io/co2-calculator-user-doc/fr/external-cloud/)",
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

  // CHARTS external-cloud-and-ai.charts-title
  [`${MODULES.ExternalCloudAndAI}-charts-title`]: {
    en: 'External cloud emissions CHARTS',
    fr: 'Émissions du cloud externe CHARTS',
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
