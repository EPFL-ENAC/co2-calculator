import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';

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
    label: 'kg CO₂-éq',
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
      name: 'Cloud Services',
      moduleFields: cloudFields,
    },
  ],
};
