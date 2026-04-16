import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { formatTonnesCO2 } from 'src/utils/number';
import {
  SUBMODULE_EXTERNAL_CLOUD_TYPES,
  MODULES,
  MODULES_THRESHOLD_TYPES,
} from 'src/constant/modules';
import type { ExternalCloudSubType } from 'src/constant/modules';
import type { Module } from 'src/constant/modules';

const cloudFields: ModuleField[] = [
  {
    id: 'provider',
    optionsId: 'kind',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.provider`,
    hideIn: { form: false },
    sortable: true,
    type: 'select',
    required: true,
    align: 'left',
    // tooltip: 'Class can be edited via the Edit button only',
    inputTypeName: 'QSelect',
    readOnly: false,
    editableInline: true,
    ratio: '1/2',
    icon: 'o_category',
  },
  {
    id: 'service_type',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.service_type`,
    hideIn: { form: false },
    optionsId: 'subkind',
    inputTypeName: 'QSelect',
    sortable: true,
    type: 'select',
    required: true,
    placeholder: 'e.g., Compute, Storage, Database (placeholder i18n)',
    align: 'left',
    readOnly: false,
    editableInline: true,
    ratio: '1/2',
    icon: 'o_category',
  },
  // {
  //   id: 'region',
  //   labelKey: `${MODULES.ExternalCloudAndAI}.inputs.region`,
  //   type: 'text',
  //   hideIn: { form: false },
  //   sortable: true,
  // },
  {
    id: 'spent_amount',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.spent_amount`,
    type: 'number',
    editableInline: true,
    min: 0,
    step: 0.01,
    ratio: '3/4',
    hideIn: { form: false },
    sortable: true,
  },
  {
    id: 'currency',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.currency`,
    hint: `${MODULES.ExternalCloudAndAI}.inputs.currency-hint`,
    type: 'select',
    ratio: '1/4',
    editableInline: true,
    hideIn: { form: false },
    sortable: true,
    options: [
      { value: 'eur', label: 'EUR' },
      { value: 'chf', label: 'CHF' },
      { value: 'usd', label: 'USD' },
    ],
  },
  {
    id: 'kg_co2eq',
    labelKey: 'results_units_kg',
    type: 'number',
    hideIn: { form: true },
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
    id: 'provider',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.provider`,
    required: true,
    ratio: '4/12',
    hideIn: { table: false },
    editableInline: true,

    optionsId: 'kind',
    inputTypeName: 'QSelect',
    sortable: true,
    type: 'select',
  },
  {
    id: 'usage_type',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.usage_type`,
    required: true,
    ratio: '4/12',
    hideIn: { table: false },
    editableInline: true,

    optionsId: 'subkind',
    inputTypeName: 'QSelect',
    sortable: true,
    type: 'select',
  },
  {
    id: 'user_count',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.user_count`,
    type: 'number',
    required: true,
    editableInline: true,
    min: 1,
    step: 1,
    ratio: '4/12',
    sortable: true,
    hideIn: { table: false },
    defaultFrom: 'total_fte',
  },
  {
    id: 'requests_per_user_per_day',
    labelKey: `${MODULES.ExternalCloudAndAI}.inputs.requests_per_user_per_day`,
    type: 'select',
    required: true,
    editableInline: true,
    inputTypeName: 'QSelect',
    optionLabelsAreKeys: true,
    ratio: '4/12',
    sortable: true,
    hideIn: { table: false },
    options: [
      {
        value: '1-5 times per day',
        label: `${MODULES.ExternalCloudAndAI}.inputs.requests_frequency.1_5`,
      },
      {
        value: '5-20 times per day',
        label: `${MODULES.ExternalCloudAndAI}.inputs.requests_frequency.5_20`,
      },
      {
        value: '20-100 times per day',
        label: `${MODULES.ExternalCloudAndAI}.inputs.requests_frequency.20_100`,
      },
      {
        value: '>100 times per day',
        label: `${MODULES.ExternalCloudAndAI}.inputs.requests_frequency.gt_100`,
      },
    ],
  },
  {
    id: 'kg_co2eq',
    labelKey: 'results_units_kg',
    type: 'number',
    hideIn: { form: true },
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
  hasTooltipSubText: true,
  description: 'Track external cloud services and AI usage',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  threshold: {
    type: MODULES_THRESHOLD_TYPES[0],
    value: 500, // kg CO₂-eq; implicit coloring only
  },
  numberFormatOptions: {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  },
  totalFormatter: formatTonnesCO2,
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
