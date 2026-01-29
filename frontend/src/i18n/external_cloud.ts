import { MODULES } from 'src/constant/modules';

export default {
  [MODULES.ExternalCloudAndAI]: {
    en: 'External clouds',
    fr: 'Clouds externes',
  },
  [`${MODULES.ExternalCloudAndAI}-description`]: {
    en: 'Enter external clouds usage data to estimate the carbon footprint.',
    fr: "Saisissez vos données relatives à l'utilisation de clouds externes pour estimer leur empreinte carbone.",
  },
  [`${MODULES.ExternalCloudAndAI}-title-subtext`]: {
    en: 'This module calculates the carbon footprint associated with the use of cloud services, all features combined. Data entry is manual and can be reviewed and added or deleted by the user.\nSome cells may or may not be editable depending on the type of service selected.',
    fr: "Ce module calcule l'empreinte carbone liée à l'utilisation de clouds externes, toutes fonctionnalités confondues. La saisie des informations est manuelle. Vous pouvez consulter, ajouter ou supprimer des entrées selon vos besoins.\nCertaines cellules seront ou non éditables en fonction du type de service sélectionné.",
  },
  [`${MODULES.ExternalCloudAndAI}-title-tooltip-title`]: {
    en: 'You can add data one at a time using the Add button below, or upload several entries at once using a file that follows the template.',
    fr: 'Vous pouvez ajouter les données une par une en utilisant le bouton « Ajouter » ci-dessous, ou importer plusieurs entrées à la fois via un fichier respectant le modèle fourni.',
  },

  // CHARTS external-cloud-and-ai.charts-title
  [`${MODULES.ExternalCloudAndAI}-charts-title`]: {
    en: 'External Cloud Emissions',
    fr: 'Émissions du cloud externe',
  },
  // external-cloud-and-ai.cloud_services_table_title
  [`${MODULES.ExternalCloudAndAI}.cloud_services_table_title`]: {
    en: 'Cloud Service ({count}) | Cloud Services ({count})',
    fr: 'Service Cloud ({count}) | Services Cloud ({count})',
  },

  // external-cloud-and-ai.ai_usage_table_title
  [`${MODULES.ExternalCloudAndAI}.ai_usage_table_title`]: {
    en: 'AI Usage ({count}) | AI Usages ({count})',
    fr: "Utilisation de l'IA ({count}) | Utilisations de l'IA ({count})",
  },
  // CLOUD SUBMODULE
  [`${MODULES.ExternalCloudAndAI}.inputs.service_type`]: {
    en: 'Service Type',
    fr: 'Type de service',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.cloud_provider`]: {
    en: 'Cloud Provider',
    fr: 'Fournisseur de services cloud',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.region`]: {
    en: 'Region',
    fr: 'Région',
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.spending`]: {
    en: 'Spending',
    fr: 'Dépenses',
  },
  // Co2eq is the same in both languages is using common key
  // AI SUBMODULE
  [`${MODULES.ExternalCloudAndAI}.inputs.ai_provider`]: {
    en: 'AI Provider',
    fr: "Fournisseur d'IA",
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.ai_use`]: {
    en: 'AI Use',
    fr: "Utilisation de l'IA",
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.frequency_use_per_day`]: {
    en: 'Frequency of Use per Day',
    fr: "Fréquence d'utilisation par jour",
  },
  [`${MODULES.ExternalCloudAndAI}.inputs.user_count`]: {
    en: 'User Count',
    fr: "Nombre d'utilisateurs",
  },
} as const;
