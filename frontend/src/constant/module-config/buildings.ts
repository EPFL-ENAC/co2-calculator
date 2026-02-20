import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { SUBMODULE_BUILDINGS_TYPES } from 'src/constant/modules';
import { formatTonnesCO2 } from 'src/utils/number';
import type { BuildingsSubType } from 'src/constant/modules';

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
    labelKey: 'results_units_kg',
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

export const buildings: ModuleConfig = {
  id: 'module_buildings_001',
  type: 'buildings',
  name: 'Buildings',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description: 'Track building-related emissions',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  totalFormatter: formatTonnesCO2,
  submodules: [
    {
      id: 'sub_building',
      type: SUBMODULE_BUILDINGS_TYPES.Building as BuildingsSubType,
      name: 'Building',
      moduleFields: buildingFields,
    },
  ],
};
