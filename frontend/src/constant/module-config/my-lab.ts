import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';

const potableFields: ModuleField[] = [
  {
    id: 'source',
    label: 'Source',
    type: 'text',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'consumption',
    label: 'Consumption (m³)',
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
    id: 'potable_monthly',
    label: 'Monthly Consumption (m³)',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: true },
  },
];

const wastewaterFields: ModuleField[] = [
  {
    id: 'treatment',
    label: 'Treatment Type',
    type: 'text',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'volume',
    label: 'Volume (m³)',
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
    id: 'waste_monthly',
    label: 'Monthly Volume (m³)',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: true },
  },
];

export const myLab: ModuleConfig = {
  id: 'module_water_001',
  type: 'my-lab',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
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
      moduleFields: potableFields,
    },
    {
      id: 'sub_wastewater',
      name: 'Wastewater',
      count: 1,
      moduleFields: wastewaterFields,
    },
  ],
};
