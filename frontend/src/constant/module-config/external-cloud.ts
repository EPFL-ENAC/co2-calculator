import { ModuleConfig } from 'src/constant/moduleConfig';

export const externalCloud: ModuleConfig = {
  id: 'module_external_cloud_001',
  type: 'external-cloud',
  name: 'External Cloud',
  description: 'Track external cloud services usage',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  submodules: [
    {
      id: 'sub_cloud_services',
      name: 'Cloud Services',
      tableColumns: [
        { key: 'service', label: 'Service', type: 'text', sortable: true },
        { key: 'usage', label: 'Usage', type: 'number', sortable: true },
        { key: 'kg_co2eq', label: 'kg CO2-eq', type: 'number', sortable: true },
      ],
      formInputs: [
        {
          id: 'cloud_service',
          label: 'Service Name',
          type: 'text',
          required: true,
        },
      ],
    },
  ],
};
