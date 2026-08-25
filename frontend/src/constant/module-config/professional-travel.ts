import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { MODULES, MODULES_THRESHOLD_TYPES } from 'src/constant/modules';
import { formatTonnesCO2 } from 'src/utils/number';
import type { ProfessionalTravelSubType } from 'src/constant/modules';

// "Other traveler" sentinels + resolver live in a standalone light module so
// they stay unit-testable (issue #1153); re-exported here for convenience.
import { TRAVELER_OTHER_INTERNAL } from 'src/constant/module-config/traveler-options';
export {
  TRAVELER_OTHER_INTERNAL,
  TRAVELER_OTHER_EXTERNAL,
  TRAVELER_OTHER_INTERNAL_LABEL_KEY,
  TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
  resolveTravelerName,
} from 'src/constant/module-config/traveler-options';

const commonTravelFields: ModuleField[] = [
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
    id: 'origin_iata',
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
    id: 'destination_iata',
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
    editableInline: true,
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
    id: 'user_institutional_id',
    labelKey: `${MODULES.ProfessionalTravel}-field-traveler`,
    type: 'headcount-member-select',
    required: false,
    sortable: false,
    ratio: '1/1',
    editableInline: false,
    // Explorer has no headcount roster of its own to pick a traveler from,
    // so default to the "Other traveler (internal)" sentinel.
    explorerDefault: TRAVELER_OTHER_INTERNAL,
    hideIn: {
      table: true,
    },
  },
  {
    id: 'traveler_name',
    labelKey: `${MODULES.ProfessionalTravel}-field-traveler`,
    type: 'text',
    readOnly: true,
    sortable: true,
    ratio: '1/1',
    editableInline: false,
    hideIn: {
      form: true,
    },
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
];

// Emissions column, kept separate so the class column can be placed just before it.
const emissionsField: ModuleField = {
  id: 'kg_co2eq',
  align: 'right',
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
};

const planeCabinClassField: ModuleField = {
  id: 'cabin_class',
  labelKey: `${MODULES.ProfessionalTravel}-field-class`,
  type: 'select',
  required: true,
  sortable: true,
  ratio: '1/1',
  editableInline: true,
  optionLabelsAreKeys: true,
  options: [
    { value: 'business', label: 'charts-business-class-subcategory' },
    { value: 'economy', label: 'charts-eco-class-subcategory' },
  ],
};

const planeFields: ModuleField[] = buildTravelFields(
  {
    id: 'origin_name',
    labelKey: `${MODULES.ProfessionalTravel}-field-from`,
    columnSize: 'lg',
  },
  {
    id: 'destination_name',
    labelKey: `${MODULES.ProfessionalTravel}-field-to`,
    columnSize: 'lg',
  },
  planeCabinClassField,
);

const trainLocationTooltip = `${MODULES.ProfessionalTravel}-train-location-local-language-tooltip`;

const trainCabinClassField: ModuleField = {
  id: 'cabin_class',
  labelKey: `${MODULES.ProfessionalTravel}-field-class`,
  type: 'select',
  required: true,
  sortable: true,
  ratio: '1/1',
  editableInline: true,
  optionLabelsAreKeys: true,
  options: [
    { value: 'first', label: 'class_1' },
    { value: 'second', label: 'class_2' },
  ],
};

const trainFields: ModuleField[] = buildTravelFields(
  {
    id: 'origin_name',
    labelKey: `${MODULES.ProfessionalTravel}-field-from`,
    tooltip: trainLocationTooltip,
    columnSize: 'lg',
  },
  {
    id: 'destination_name',
    labelKey: `${MODULES.ProfessionalTravel}-field-to`,
    tooltip: trainLocationTooltip,
    columnSize: 'lg',
  },
  trainCabinClassField,
  { directionInputTooltip: trainLocationTooltip },
);

export const professionalTravel: ModuleConfig = {
  id: 'module_travel_001',
  type: 'professional-travel',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  numberFormatOptions: {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  },
  totalFormatter: formatTonnesCO2,
  unit: 't CO₂-eq',
  threshold: {
    type: MODULES_THRESHOLD_TYPES[0],
    value: 1000,
  },
  submodules: [
    {
      id: 'plane',
      type: 'plane' as ProfessionalTravelSubType,
      tableNameKey: `${MODULES.ProfessionalTravel}-plane-table-title`,
      moduleFields: planeFields,
      requiredFieldIds: [
        'origin_iata',
        'destination_iata',
        'user_institutional_id',
        'cabin_class',
      ],
      csvTemplateHeaders: [
        'from',
        'to',
        'departure_date',
        'number_of_trips',
        'user_institutional_id',
        'cabin_class',
      ],
      hasTableTopBar: true,
      hasTablePagination: true,
      hasTableAction: true,
      topVisualization: 'trips-map',
      addButtonLabelKey: `${MODULES.ProfessionalTravel}-add-plane-button`,
    },
    {
      id: 'train',
      type: 'train' as ProfessionalTravelSubType,
      tableNameKey: `${MODULES.ProfessionalTravel}-train-table-title`,
      moduleFields: trainFields,
      requiredFieldIds: [
        'origin_name',
        'destination_name',
        'user_institutional_id',
        'cabin_class',
      ],
      csvTemplateHeaders: [
        'origin_name',
        'destination_name',
        'departure_date',
        'number_of_trips',
        'user_institutional_id',
        'cabin_class',
      ],
      hasTableTopBar: true,
      hasTablePagination: true,
      hasTableAction: true,
      topVisualization: 'trips-map',
      addButtonLabelKey: `${MODULES.ProfessionalTravel}-add-train-button`,
    },
  ],
} as ModuleConfig & { unit?: string };

function buildTravelFields(
  origin: {
    id: string;
    labelKey: string;
    tooltip?: string;
    columnSize?: ModuleField['columnSize'];
  },
  destination: {
    id: string;
    labelKey: string;
    tooltip?: string;
    columnSize?: ModuleField['columnSize'];
  },
  classField: ModuleField,
  options?: { directionInputTooltip?: string },
): ModuleField[] {
  return [
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
      hideIn: { table: true },
      tooltip: options?.directionInputTooltip,
    },
    {
      id: origin.id,
      labelKey: origin.labelKey,
      type: 'text',
      required: true,
      sortable: true,
      ratio: '1/1',
      editableInline: false,
      hideIn: { form: true },
      tooltip: origin.tooltip,
      columnSize: origin.columnSize,
    },
    {
      id: destination.id,
      labelKey: destination.labelKey,
      type: 'text',
      required: true,
      sortable: true,
      ratio: '1/1',
      editableInline: false,
      hideIn: { form: true },
      tooltip: destination.tooltip,
      columnSize: destination.columnSize,
    },
    ...commonTravelFields.slice(3),
    classField,
    emissionsField,
  ];
}
