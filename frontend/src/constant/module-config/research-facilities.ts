import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { SUBMODULE_RESEARCH_FACILITIES_TYPES } from 'src/constant/modules';
import { formatTonnesCO2 } from 'src/utils/number';

import type { AllSubmoduleTypes } from 'src/constant/modules';
const rootFields: ModuleField[] = [
  {
    id: 'waste_general',
    label: 'General Waste (kg/month)',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: true },
  },
  {
    id: 'waste_recycling',
    label: 'Recyclable Waste (kg/month)',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: true },
  },
  {
    id: 'waste_organic',
    label: 'Organic Waste (kg/month)',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: true },
  },
  {
    id: 'waste_hazardous',
    label: 'Hazardous Waste (kg/month)',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: true },
  },
];

const generalWasteFields: ModuleField[] = [
  {
    id: 'date',
    label: 'Date',
    type: 'date',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'weight',
    label: 'Weight (kg)',
    type: 'number',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'disposal',
    label: 'Disposal Method',
    type: 'text',
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
];

const recyclingFields: ModuleField[] = [
  {
    id: 'material',
    label: 'Material',
    type: 'text',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'weight',
    label: 'Weight (kg)',
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
];

export const researchFacilities: ModuleConfig = {
  id: 'module_waste_001',
  type: 'research-facilities',
  name: 'Waste Management',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description: 'Categorize and track waste streams',
  hasSubmodules: true,
  formStructure: 'single',
  totalFormatter: formatTonnesCO2,
  moduleFields: rootFields,
  submodules: [
    {
      id: 'sub_general_waste',
      type: SUBMODULE_RESEARCH_FACILITIES_TYPES.ResarchFacilities as AllSubmoduleTypes,
      name: 'General Waste',
      moduleFields: generalWasteFields,
    },
    {
      id: 'sub_recycling',
      type: SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities as AllSubmoduleTypes,
      name: 'Recycling',
      moduleFields: recyclingFields,
    },
  ],
};
