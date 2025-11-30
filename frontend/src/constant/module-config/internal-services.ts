import { ModuleConfig } from 'src/constant/moduleConfig';

export const internalServices: ModuleConfig = {
  id: 'module_waste_001',
  type: 'internal-services',
  name: 'Waste Management',
  description: 'Categorize and track waste streams',
  hasSubmodules: true,
  formStructure: 'single',
  formInputs: [
    {
      id: 'waste_general',
      label: 'General Waste (kg/month)',
      type: 'number',
      required: true,
      min: 0,
    },
    {
      id: 'waste_recycling',
      label: 'Recyclable Waste (kg/month)',
      type: 'number',
      required: true,
      min: 0,
    },
    {
      id: 'waste_organic',
      label: 'Organic Waste (kg/month)',
      type: 'number',
      required: true,
      min: 0,
    },
    {
      id: 'waste_hazardous',
      label: 'Hazardous Waste (kg/month)',
      type: 'number',
      required: true,
      min: 0,
    },
  ],
  submodules: [
    {
      id: 'sub_general_waste',
      name: 'General Waste',
      tableColumns: [
        { key: 'date', label: 'Date', type: 'date', sortable: true },
        { key: 'weight', label: 'Weight (kg)', type: 'number', sortable: true },
        {
          key: 'disposal',
          label: 'Disposal Method',
          type: 'text',
          sortable: true,
        },
        { key: 'kg_co2eq', label: 'kg CO2-eq', type: 'number', sortable: true },
      ],
    },
    {
      id: 'sub_recycling',
      name: 'Recycling',
      tableColumns: [
        { key: 'material', label: 'Material', type: 'text', sortable: true },
        { key: 'weight', label: 'Weight (kg)', type: 'number', sortable: true },
        { key: 'kg_co2eq', label: 'kg CO2-eq', type: 'number', sortable: true },
      ],
    },
    {
      id: 'sub_organic',
      name: 'Organic Waste',
      tableColumns: [
        { key: 'date', label: 'Date', type: 'date', sortable: true },
        { key: 'weight', label: 'Weight (kg)', type: 'number', sortable: true },
        { key: 'treatment', label: 'Treatment', type: 'text', sortable: true },
        { key: 'kg_co2eq', label: 'kg CO2-eq', type: 'number', sortable: true },
      ],
    },
  ],
};
