import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';

const buildingFields: ModuleField[] = [
  {
    id: 'item',
    label: 'Item',
    type: 'text',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'value',
    label: 'Value',
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
    id: 'building_input',
    label: 'Building Input',
    type: 'text',
    required: true,
    hideIn: { table: true },
  },
];

export const infrastructure: ModuleConfig = {
  id: 'module_infrastructure_001',
  type: 'infrastructure',
  name: 'Infrastructure',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description: 'Track infrastructure-related emissions',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  submodules: [
    {
      id: 'sub_building',
      name: 'Building',
      moduleFields: buildingFields,
    },
  ],
};
