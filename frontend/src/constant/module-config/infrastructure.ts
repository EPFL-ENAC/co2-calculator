import { ModuleConfig } from 'src/constant/moduleConfig';

export const infrastructure: ModuleConfig = {
  id: 'module_infrastructure_001',
  type: 'infrastructure',
  name: 'Infrastructure',
  description: 'Track infrastructure-related emissions',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  submodules: [
    {
      id: 'sub_building',
      name: 'Building',
      tableColumns: [
        { key: 'item', label: 'Item', type: 'text', sortable: true },
        { key: 'value', label: 'Value', type: 'number', sortable: true },
        { key: 'kgCO2eq', label: 'kg CO2-eq', type: 'number', sortable: true },
      ],
      formInputs: [
        {
          id: 'building_input',
          label: 'Building Input',
          type: 'text',
          required: true,
        },
      ],
    },
  ],
};
