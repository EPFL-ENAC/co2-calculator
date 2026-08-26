import { ModuleConfig, ModuleField } from '@/constant/moduleConfig';
import {
  MODULES,
  SUBMODULE_RESEARCH_FACILITIES_TYPES,
} from '@/constant/modules';
import { formatTonnesCO2 } from '@/utils/number';
import type { Module, ResearchFacilitiesSubType } from '@/constant/modules';

// #2007: manual entry picks a platform from the year's factor catalog — the id
// is the factor's classification key, the name is only its label. Free-typing
// either would resolve no factor, so the select carries the id and mirrors the
// name back into the payload.
const facilityIdField: ModuleField = {
  id: 'researchfacility_id',
  labelKey: `${MODULES.ResearchFacilities}.inputs.name`,
  type: 'select',
  optionsId: 'kind',
  optionsLabelField: 'researchfacility_name',
  inputTypeName: 'QSelect',
  required: true,
  align: 'left',
  hideIn: { table: true },
  icon: 'o_biotech',
  columnSize: 'lg',
};

const researchFacilitiesFields: ModuleField[] = [
  { ...facilityIdField, ratio: '1/3' },
  {
    id: 'researchfacility_name',
    labelKey: `${MODULES.ResearchFacilities}.inputs.name`,
    type: 'text',
    editableInline: true,
    required: true,
    sortable: true,
    align: 'left',
    ratio: '1/4',
    hideIn: { form: true },
    tooltip:
      'module-research-facilities-submodule-research-facilities-table-researchfacility_name',
  },
  {
    id: 'use',
    labelKey: `${MODULES.ResearchFacilities}.inputs.use`,
    type: 'number',
    required: true,
    min: 0,
    // #2007 — mirrors backend USE_BOUNDS: `use` means a share, machine time,
    // spend or housings depending on the platform's unit.
    conditionalBounds: {
      fieldId: 'use_unit',
      byValue: {
        '%': { max: 100 },
        // 168 h/week x 52 weeks — the backend derives this from
        // HOURS_PER_WEEK x WEEKS_PER_YEAR, the same pair the equipment module
        // computes with. Not the calendar's 8760.
        hours: { max: 8736 },
        housings: { integer: true },
      },
    },
    editableInline: true,
    ratio: '1/3',
    hideIn: { form: false },
    sortable: true,
    tooltip:
      'module-research-facilities-submodule-research-facilities-table-use',
  },
  {
    id: 'use_unit',
    labelKey: `${MODULES.ResearchFacilities}.inputs.use_unit`,
    type: 'text',
    required: true,
    // Mirrored from the selected factor: the emission formula only resolves
    // when the entry's unit string-equals the factor's, so it is never typed.
    readOnly: true,
    editableInline: false,
    ratio: '1/3',
    hideIn: { form: false },
    sortable: true,
    tooltip:
      'module-research-facilities-submodule-research-facilities-table-use_unit',
  },
  {
    id: 'kg_co2eq',
    align: 'right',
    labelKey: 'results_units_kg',
    type: 'number',
    hideIn: { form: true },
    sortable: true,
    tooltip:
      'module-research-facilities-submodule-research-facilities-table-kg_co2eq',
  },
];

const animalFields: ModuleField[] = [
  { ...facilityIdField, ratio: '1/4' },
  {
    id: 'researchfacility_name',
    labelKey: `${MODULES.ResearchFacilities}.inputs.name`,
    type: 'text',
    editableInline: true,
    required: true,
    sortable: true,
    align: 'left',
    ratio: '1/5',
    hideIn: { form: true },
    tooltip:
      'module-research-facilities-submodule-animal_facilities-table-researchfacility_name',
  },
  {
    id: 'researchfacility_type',
    labelKey: `${MODULES.ResearchFacilities}.inputs.type`,
    type: 'select',
    optionsId: 'subkind',
    inputTypeName: 'QSelect',
    optionLabelKey: `${MODULES.ResearchFacilities}.type.{value}`,
    required: true,
    editableInline: false,
    // #951: not named in the matrix (Research facilities/Use/Unit only) —
    // stays locked even on a user's own row. Create scope is wider than the
    // update whitelist: the animal create DTO requires it (#2007).
    ratio: '1/4',
    hideIn: { form: false },
    sortable: true,
    tooltip:
      'module-research-facilities-submodule-animal_facilities-table-researchfacility_type',
  },
  {
    id: 'use',
    labelKey: `${MODULES.ResearchFacilities}.inputs.nb_housing`,
    type: 'number',
    required: true,
    min: 0,
    // #2007 — mirrors backend USE_BOUNDS: `use` means a share, machine time,
    // spend or housings depending on the platform's unit.
    conditionalBounds: {
      fieldId: 'use_unit',
      byValue: {
        '%': { max: 100 },
        // 168 h/week x 52 weeks — the backend derives this from
        // HOURS_PER_WEEK x WEEKS_PER_YEAR, the same pair the equipment module
        // computes with. Not the calendar's 8760.
        hours: { max: 8736 },
        housings: { integer: true },
      },
    },
    editableInline: true,
    ratio: '1/4',
    hideIn: { form: false },
    sortable: true,
    tooltip: 'module-research-facilities-submodule-animal_facilities-table-use',
  },
  {
    id: 'use_unit',
    labelKey: `${MODULES.ResearchFacilities}.inputs.use_unit`,
    type: 'text',
    required: true,
    // Same factor-mirroring rule as the common submodule; no table column.
    readOnly: true,
    ratio: '1/4',
    hideIn: { table: true },
  },
  {
    id: 'kg_co2eq',
    align: 'right',
    labelKey: 'results_units_kg',
    type: 'number',
    hideIn: { form: true },
    sortable: true,
    tooltip:
      'module-research-facilities-submodule-animal_facilities-table-kg_co2eq',
  },
];

export const researchFacilities: ModuleConfig = {
  id: 'module_research_facilities_001',
  type: MODULES.ResearchFacilities as Module,
  name: 'Research Facilities',
  hasDescription: true,
  hasDescriptionSubtext: true,
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
      hasTableAction: true,
      hasTableNote: true,
      addButtonLabelKey: `${MODULES.ResearchFacilities}.add_button`,
    },
    {
      id: SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities,
      type: SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities as ResearchFacilitiesSubType,
      tableNameKey: `${MODULES.ResearchFacilities}.${SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities}-table-title`,
      moduleFields: animalFields,
      hasTableAction: true,
      hasTableNote: true,
      addButtonLabelKey: `${MODULES.ResearchFacilities}.add_button`,
    },
  ],
};
