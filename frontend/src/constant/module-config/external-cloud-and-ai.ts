import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { SUBMODULE_EXTERNAL_CLOUD_TYPES,  MODULES, MODULES_THRESHOLD_TYPES } from 'src/constant/modules';
import type { ExternalCloudSubType } from 'src/constant/modules';
import type { Module } from 'src/constant/modules';

const cloudFields: ModuleField[] = [
  {
    id: 'service_type',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.service_type`,
    type: 'text',
    required: true,
    placeholder: 'e.g., Compute, Storage, Database (placeholder i18n)',
    sortable: true,
    align: 'left',
    readOnly: true,
    hideIn: { form: false },
    ratio: '1/1',
  },
  {
    id: 'cloud_provider',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.cloud_provider`,
    type: 'text',
    hideIn: { form: false },
    sortable: true,
  },
  {
    id: 'region',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.region`,
    type: 'text',
    hideIn: { form: false },
    sortable: true,
  },
  {
    id: 'spending',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.spending`,
    type: 'number',
    hideIn: { form: false },
    sortable: true,
  },
  {
    id: 'kg_co2eq',
    label: 'kg CO₂-eq',
    type: 'number',
    hideIn: { form: false },
    sortable: true,
  },
];

// class ExternalAIHandlerResponse(DataEntryResponseGen):
//     # ai_provider,ai_use,frequency_use_per_day,user_count
//     ai_provider: str
//     ai_use: str
//     frequency_use_per_day: int
//     user_count: int
//     kg_co2eq: float

const externalAIFields: ModuleField[] = [
  {
    id: 'ai_provider',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.ai_provider`,
    type: 'text',
    required: true,
    ratio: '4/12',
    hideIn: { table: false },
  },
  {
    id: 'ai_use',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.ai_use`,
    type: 'text',
    required: true,
    ratio: '4/12',
    hideIn: { table: false },
  },
  {
    id: 'frequency_use_per_day',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.frequency_use_per_day`,
    type: 'number',
    required: true,
    min: 1,
    step: 1,
    ratio: '4/12',
    hideIn: { table: false },
  },
  {
    id: 'user_count',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.user_count`,
    type: 'number',
    required: true,
    min: 1,
    step: 1,
    ratio: '4/12',
    hideIn: { table: false },
  },
  {
    id: 'kg_co2eq',
    label: 'kg CO₂-eq',
    type: 'number',
    hideIn: { form: false },
    sortable: true,
    ratio: '4/12',
  },
];

export const externalCloudAndAi: ModuleConfig = {
  id: 'module_external_cloud_001',
  type: MODULES.ExternalCloudAndAI as Module,
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description: 'Track external cloud services and AI usage',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
    threshold: {
    type: MODULES_THRESHOLD_TYPES[0],
    value: 1000000, // kg CO₂-eq; implicit coloring only
  },
  submodules: [
    {
      id: SUBMODULE_EXTERNAL_CLOUD_TYPES.external_clouds,
      type: SUBMODULE_EXTERNAL_CLOUD_TYPES.external_clouds as ExternalCloudSubType,
      tableNameKey: `${MODULES.ExternalCloudAndAI}.cloud_services_table_title`,
      moduleFields: cloudFields,
    },
    {
      id: SUBMODULE_EXTERNAL_CLOUD_TYPES.external_ai,
      type: SUBMODULE_EXTERNAL_CLOUD_TYPES.external_ai as ExternalCloudSubType,
      tableNameKey: `${MODULES.ExternalCloudAndAI}.ai_usage_table_title`,
      moduleFields: externalAIFields,
    },
  ],
};
