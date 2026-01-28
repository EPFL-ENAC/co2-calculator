import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';

export default {
  [MODULES.ExternalCloudAndAI]: {
    en: 'External Cloud and AI',
    fr: 'Cloud externe et IA',
  },
  [MODULES_DESCRIPTIONS.ExternalCloudAndAI]: {
    en: 'Measure cloud computing emissions from external service providers.',
    fr: "Mesurez les émissions liées à l'informatique en nuage auprès de fournisseurs externes.",
  },
  // CHARTS external-cloud-and-ai.charts-title
  [`${MODULES.ExternalCloudAndAI}-charts-title`]: { 
    en: 'External Cloud and AI Emissions',
    fr: 'Émissions du cloud externe et de l\'IA',
   },
  // external-cloud-and-ai.cloud_services_table_title
  [`${MODULES.ExternalCloudAndAI}.cloud_services_table_title`]: { 
    en: 'Cloud Services',
    fr: 'Services Cloud',
   },
   // external-cloud-and-ai.ai_usage_table_title
  [`${MODULES.ExternalCloudAndAI}.ai_usage_table_title`]: { 
    en: 'AI Usage',
    fr: 'Utilisation de l\'IA',
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
    fr: 'Fournisseur d\'IA',
   },
  [`${MODULES.ExternalCloudAndAI}.inputs.ai_use`]: { 
    en: 'AI Use',
    fr: 'Utilisation de l\'IA',
   },
  [`${MODULES.ExternalCloudAndAI}.inputs.frequency_use_per_day`]: { 
    en: 'Frequency of Use per Day',
    fr: 'Fréquence d\'utilisation par jour',
   },
  [`${MODULES.ExternalCloudAndAI}.inputs.user_count`]: { 
    en: 'User Count',
    fr: 'Nombre d\'utilisateurs',
   },


} as const;
