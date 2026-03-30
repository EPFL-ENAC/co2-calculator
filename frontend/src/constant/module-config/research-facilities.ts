import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import {
  MODULES,
  SUBMODULE_RESEARCH_FACILITIES_TYPES,
} from 'src/constant/modules';
import { formatTonnesCO2 } from 'src/utils/number';
import type { Module, ResearchFacilitiesSubType } from 'src/constant/modules';

const researchFacilitiesFields: ModuleField[] = [
  {
    id: 'researchfacility_name',
    labelKey: `${MODULES.ResearchFacilities}.inputs.name`,
    type: 'text',
    editableInline: false,
    required: true,
    sortable: true,
    align: 'left',
    ratio: '1/4',
    hideIn: { form: true },
  },
  {
    id: 'use',
    labelKey: `${MODULES.ResearchFacilities}.inputs.use`,
    type: 'text',
    editableInline: false,
    ratio: '1/4',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'use_unit',
    labelKey: `${MODULES.ResearchFacilities}.inputs.use_unit`,
    type: 'text',
    editableInline: false,
    ratio: '1/4',
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

const animalFields: ModuleField[] = [
  {
    id: 'researchfacility_name',
    labelKey: `${MODULES.ResearchFacilities}.inputs.name`,
    type: 'text',
    editableInline: false,
    required: true,
    sortable: true,
    align: 'left',
    ratio: '1/5',
    hideIn: { form: true },
  },
  {
    id: 'researchfacility_type',
    labelKey: `${MODULES.ResearchFacilities}.inputs.type`,
    type: 'text',
    editableInline: false,
    ratio: '1/5',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'use',
    labelKey: `${MODULES.ResearchFacilities}.inputs.nb_housing`,
    type: 'text',
    editableInline: false,
    ratio: '1/5',
    hideIn: { form: true },
    sortable: true,
    tooltip: `${MODULES.ResearchFacilities}.inputs.housing_nb-tooltip`,
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
  id: 'module_research_facilities_001',
  type: MODULES.ResearchFacilities as Module,
  name: 'Research Facilities',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description:
    'This module estimates the carbon footprint of research facilities, including animal facilities.',
  hasSubmodules: true,
  formStructure: 'single',
  totalFormatter: formatTonnesCO2,
  submodules: [
    {
      id: SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities,
      type: SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities as ResearchFacilitiesSubType,
      tableNameKey: `${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities}-table-title`,
      moduleFields: researchFacilitiesFields,
      hasFormTooltip: false,
      hasTableAction: false,
    },
    {
      id: SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities,
      type: SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities as ResearchFacilitiesSubType,
      tableNameKey: `${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities}-table-title`,
      moduleFields: animalFields,
      hasFormTooltip: false,
      hasTableAction: false,
    },
  ],
};
