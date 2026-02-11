import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { MODULES, MODULES_THRESHOLD_TYPES } from 'src/constant/modules';
import type { ProfessionalTravelSubType } from 'src/constant/modules';

const moduleFields: ModuleField[] = [
  {
    id: 'transport_mode',
    labelKey: `${MODULES.ProfessionalTravel}-field-type`,
    type: 'radio-group',
    required: true,
    sortable: true,
    ratio: '2/12',
    options: [
      { value: 'train', label: 'Train' },
      { value: 'plane', label: 'Flight' },
    ],
    editableInline: false,
  },
  {
    id: 'round_trip',
    labelKey: [
      `${MODULES.ProfessionalTravel}-field-from`,
      `${MODULES.ProfessionalTravel}-field-to`,
    ],
    type: 'direction-input',
    required: true,
    sortable: false,
    ratio: '1/1',
    editableInline: false,
    hideIn: {
      table: true,
    },
  },
  {
    id: 'origin',
    labelKey: `${MODULES.ProfessionalTravel}-field-from`,
    type: 'text',
    required: true,
    sortable: true,
    ratio: '1/1',
    editableInline: false,
    hideIn: {
      form: true,
    },
  },
  {
    id: 'destination',
    labelKey: `${MODULES.ProfessionalTravel}-field-to`,
    type: 'text',
    required: true,
    sortable: true,
    ratio: '1/1',
    editableInline: false,
    hideIn: {
      form: true,
    },
  },
  {
    id: 'is_round_trip',
    labelKey: `${MODULES.ProfessionalTravel}-field-round-trip`,
    type: 'checkbox',
    required: false,
    sortable: true,
    ratio: '1/1',
    editableInline: true,
    hideIn: {
      table: true,
    },
  },
  {
    id: 'departure_date',
    labelKey: `${MODULES.ProfessionalTravel}-field-start-date`,
    type: 'date',
    required: false,
    sortable: true,
    ratio: '1/1',
    editableInline: false,
  },
  {
    id: 'number_of_trips',
    labelKey: `${MODULES.ProfessionalTravel}-field-number-trips`,
    type: 'number',
    required: true,
    min: 1,
    sortable: true,
    ratio: '1/1',
    editableInline: true,
    default: 1,
  },
  {
    id: 'traveler_name',
    labelKey: `${MODULES.ProfessionalTravel}-field-traveler`,
    type: 'text',
    required: true,
    sortable: true,
    ratio: '1/1',
    editableInline: true,
  },
  {
    id: 'distance_km',
    labelKey: `${MODULES.ProfessionalTravel}-field-distance`,
    type: 'number',
    unit: 'km',
    sortable: true,
    ratio: '1/1',
    editableInline: false,
    readOnly: true,
    disable: true,
  },
  {
    id: 'kg_co2eq',
    labelKey: `${MODULES.ProfessionalTravel}-field-emissions`,
    type: 'number',
    unit: 'kg CO₂-eq',
    sortable: true,
    ratio: '1/1',
    editableInline: false,
    readOnly: true,
    hideIn: {
      form: true,
    },
  },
  {
    id: 'cabin_class',
    labelKey: `${MODULES.ProfessionalTravel}-field-class`,
    type: 'select',
    required: true,
    sortable: true,
    ratio: '1/1',
    editableInline: false,
    hideIn: {
      table: true,
    },
    options: [
      // Train classes
      { value: 'class_1', label: 'Class 1' },
      { value: 'class_2', label: 'Class 2' },
      // Plane classes
      { value: 'first', label: 'First' },
      { value: 'business', label: 'Business' },
      { value: 'eco', label: 'Eco' },
      { value: 'eco_plus', label: 'Eco+' },
    ],
    conditionalOptions: [
      // Show train classes when transport_mode is 'train'
      {
        when: { fieldId: 'transport_mode', value: 'train' },
        showOptions: ['class_2', 'class_1'],
      },
      // Show plane classes when transport_mode is 'plane'
      {
        when: { fieldId: 'transport_mode', value: 'plane' },
        showOptions: ['eco', 'eco_plus', 'business', 'first'],
      },
    ],
  },
];

export const professionalTravel: ModuleConfig = {
  id: 'module_travel_001',
  type: 'professional-travel',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  hasSubmodules: false,
  formStructure: 'perSubmodule',
  numberFormatOptions: {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  },
  unit: 't CO₂-eq',
  threshold: {
    type: MODULES_THRESHOLD_TYPES[0],
    value: 1000,
  },
  submodules: [
    {
      id: 'trips',
      type: 'trips' as ProfessionalTravelSubType,
      tableNameKey: `${MODULES.ProfessionalTravel}-table-title`,
      moduleFields,
      hasTableTopBar: true,
      hasTablePagination: true,
      hasTableAction: true,
      hasFormTooltip: `${MODULES.ProfessionalTravel}-form-tooltip`,
    },
  ],
} as ModuleConfig & { unit?: string };
