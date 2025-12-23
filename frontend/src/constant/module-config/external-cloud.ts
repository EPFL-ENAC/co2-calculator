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

export const externalCloud: ModuleConfig = {
  id: 'module_external_cloud_001',
  type: 'external-cloud',
  name: 'External Cloud',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description: 'Track external cloud services usage',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  submodules: [
    {
      id: 'sub_cloud_services',
      type: SUBMODULE_EXTERNAL_CLOUD_TYPES.IaaS as ExternalCloudSubType,
      name: 'Cloud Services',
      moduleFields: cloudFields,
    },
  ],
};
