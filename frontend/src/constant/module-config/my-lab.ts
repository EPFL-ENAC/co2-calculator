import { ModuleConfig } from 'src/constant/moduleConfig';

export const myLab: ModuleConfig = {
  id: 'module_water_001',
  type: 'my-lab',
  name: 'Water Consumption',
  description:
    'Track water usage by category and calculate environmental impact',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  submodules: [
    {
      id: 'sub_potable',
      name: 'Potable Water',
      count: 1,
      tableColumns: [
        { key: 'source', label: 'Source', type: 'text', sortable: true },
        {
          key: 'consumption',
          label: 'Consumption (m³)',
          type: 'number',
          sortable: true,
        },
        { key: 'kgCO2eq', label: 'kg CO2-eq', type: 'number', sortable: true },
      ],
      formInputs: [
        {
          id: 'potable_monthly',
          label: 'Monthly Consumption (m³)',
          type: 'number',
          required: true,
          min: 0,
        },
      ],
    },
    {
      id: 'sub_wastewater',
      name: 'Wastewater',
      count: 1,
      tableColumns: [
        {
          key: 'treatment',
          label: 'Treatment Type',
          type: 'text',
          sortable: true,
        },
        { key: 'volume', label: 'Volume (m³)', type: 'number', sortable: true },
        { key: 'kgCO2eq', label: 'kg CO2-eq', type: 'number', sortable: true },
      ],
      formInputs: [
        {
          id: 'waste_monthly',
          label: 'Monthly Volume (m³)',
          type: 'number',
          required: true,
          min: 0,
        },
      ],
    },
  ],
};
