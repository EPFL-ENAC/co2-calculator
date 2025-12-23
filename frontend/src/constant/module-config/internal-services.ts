import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { SUBMODULE_INTERNAL_SERVICES_TYPES } from 'src/constant/modules';

import type { InternalServicesSubType } from 'src/constant/modules';
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
    label: 'kg CO₂-eq',
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
    label: 'kg CO₂-eq',
    type: 'number',
    hideIn: { form: true },
    sortable: true,
  },
];

const organicFields: ModuleField[] = [
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
    id: 'treatment',
    label: 'Treatment',
    type: 'text',
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
];

export const internalServices: ModuleConfig = {
  id: 'module_waste_001',
  type: 'internal-services',
  name: 'Waste Management',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description: 'Categorize and track waste streams',
  hasSubmodules: true,
  formStructure: 'single',
  moduleFields: rootFields,
  submodules: [
    {
      id: 'sub_general_waste',
      type: SUBMODULE_INTERNAL_SERVICES_TYPES.ITSupport as InternalServicesSubType,
      name: 'General Waste',
      moduleFields: generalWasteFields,
    },
    {
      id: 'sub_recycling',
      type: SUBMODULE_INTERNAL_SERVICES_TYPES.Maintenance as InternalServicesSubType,
      name: 'Recycling',
      moduleFields: recyclingFields,
    },
    {
      id: 'sub_organic',
      type: SUBMODULE_INTERNAL_SERVICES_TYPES.Other as InternalServicesSubType,
      name: 'Organic Waste',
      moduleFields: organicFields,
    },
  ],
};
