import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { SUBMODULE_EXTERNAL_CLOUD_TYPES } from 'src/constant/modules';
import type { ExternalCloudSubType } from 'src/constant/modules';
const cloudFields: ModuleField[] = [
  {
    id: 'service',
    label: 'Service',
    type: 'text',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'usage',
    label: 'Usage',
    type: 'number',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'kg_co2eq',
    label: 'kg CO₂-eq',
    type: 'number',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'cloud_service',
    label: 'Service Name',
    type: 'text',
    required: true,
    hideIn: { table: true },
  },
];

const externalAIFields: ModuleField[] = [
  {
    id: 'ai_model',
    label: 'AI Model',
    type: 'text',
    required: true,
    hideIn: { table: true },
  },
  {
    id: 'name',
    label: 'Usage Name',
    type: 'text',
    required: true,
    hideIn: { table: true },
  }
]

export const externalCloudAndAi: ModuleConfig = {
  id: 'module_external_cloud_001',
  type: 'external-cloud-and-ai',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description: 'Track external cloud services and AI usage',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  submodules: [
    {
      id: 'external_clouds',
      type: SUBMODULE_EXTERNAL_CLOUD_TYPES.external_cloud as ExternalCloudSubType,
      tableNameKey: 'external-cloud-and-ai-cloud-services-table-title',
      moduleFields: cloudFields,
    },
    {
      id: 'external_ai',
      type: SUBMODULE_EXTERNAL_CLOUD_TYPES.external_ai as ExternalCloudSubType,
      tableNameKey: 'external-cloud-and-ai-ai-services-table-title',
      moduleFields: externalAIFields,
    }
  ],
};
