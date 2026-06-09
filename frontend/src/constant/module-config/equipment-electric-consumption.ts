import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { formatTonnesCO2 } from 'src/utils/number';
import type {
  Module,
  EquipmentElectricConsumptionSubType,
} from 'src/constant/modules';

import {
  MODULES,
  MODULES_THRESHOLD_TYPES,
  SUBMODULE_EQUIPMENT_TYPES,
} from 'src/constant/modules';

const nameField: ModuleField = {
  id: 'name',
  label: 'Equipment Name',
  labelKey: `${MODULES.EquipmentElectricConsumption}.inputs.name`,
  type: 'text',
  required: true,
  sortable: true,
  align: 'left',
  readOnly: false,
  ratio: '1/1',
};

const equipmentIdField: ModuleField = {
  id: 'equipment_id',
  label: 'Equipment ID',
  labelKey: `${MODULES.EquipmentElectricConsumption}.inputs.equipment_id`,
  type: 'text',
  required: false,
  sortable: false,
  align: 'left',
  readOnly: false,
  hideIn: {
    table: true,
  },
  ratio: '1/1',
};

const baseModuleFields: ModuleField[] = [
  {
    ...nameField,
    placeholder: `${MODULES.EquipmentElectricConsumption}.inputs.name-placeholder-scientific`,
    tooltip:
      'module-equipment-electric-consumption-submodule-scientific-table-name',
  },
  {
    ...equipmentIdField,
    placeholder: `${MODULES.EquipmentElectricConsumption}.inputs.equipment_id`,
  },
  {
    id: 'equipment_class',
    optionsId: 'kind',
    label: 'Class',
    labelKey: `${MODULES.EquipmentElectricConsumption}.inputs.class`,
    type: 'select',
    required: true,
    sortable: true,
    align: 'left',
    tooltip:
      'module-equipment-electric-consumption-submodule-scientific-table-equipment_class',
    inputTypeName: 'QSelect',
    readOnly: false,
    editableInline: true,
    ratio: '1/2',
    icon: 'o_category',
    columnSize: 'lg',
  },
  {
    id: 'sub_class',
    optionsId: 'subkind',
    label: 'Sub-class',
    labelKey: `${MODULES.EquipmentElectricConsumption}.inputs.subclass`,
    type: 'select',
    required: true,
    min: 0,
    sortable: true,
    align: 'left',
    tooltip:
      'module-equipment-electric-consumption-submodule-scientific-table-sub_class',
    inputTypeName: 'QSelect',
    editableInline: true,
    readOnly: false,
    ratio: '1/2',
    icon: 'o_category',
    columnSize: 'lg',
  },
  {
    id: 'active_usage_hours_per_week',
    label: 'Active usage',
    labelKey: `${MODULES.EquipmentElectricConsumption}.inputs.active_usage`,
    type: 'number',
    required: true,
    min: 0,
    max: 168,
    maxColumnWidth: 200,
    unit: 'hrs/wk',
    sortable: true,
    align: 'left',
    tooltip:
      'module-equipment-electric-consumption-submodule-scientific-table-active_usage_hours_per_week',
    inputTypeName: 'QInput',
    editableInline: true,
    ratio: '3/12',
    icon: 'o_donut_large',
  },
  {
    id: 'standby_usage_hours_per_week',
    label: 'Standby usage',
    labelKey: `${MODULES.EquipmentElectricConsumption}.inputs.standby_usage`,
    type: 'number',
    required: true,
    min: 0,
    max: 168,
    maxColumnWidth: 200,
    unit: 'hrs/wk',
    sortable: true,
    align: 'left',
    tooltip:
      'module-equipment-electric-consumption-submodule-scientific-table-standby_usage_hours_per_week',
    inputTypeName: 'QInput',
    editableInline: true,
    ratio: '3/12',
    icon: 'o_donut_large',
  },
  {
    id: 'active_power_w',
    label: 'Active power',
    labelKey: `${MODULES.EquipmentElectricConsumption}.inputs.active_power`,
    type: 'number',
    required: true,
    min: 0,
    unit: 'W',
    sortable: true,
    align: 'left',
    tooltip:
      'module-equipment-electric-consumption-submodule-scientific-table-active_power_w',
    readOnly: true,
    ratio: '3/12',
    icon: 'o_electric_bolt',
    hideIn: {
      form: false,
    },
    maxColumnWidth: 150,
  },
  {
    id: 'standby_power_w',
    label: 'Standby Power',
    labelKey: `${MODULES.EquipmentElectricConsumption}.inputs.standby_power`,
    type: 'number',
    required: true,
    min: 0,
    unit: 'W',
    sortable: true,
    align: 'left',
    tooltip:
      'module-equipment-electric-consumption-submodule-scientific-table-standby_power_w',
    readOnly: true,
    hideIn: {
      form: false,
    },
    editableInline: false,
    ratio: '3/12',
    icon: 'o_electric_bolt',
    maxColumnWidth: 150,
  },
  {
    id: 'kg_co2eq',
    labelKey: 'results_units_kg',
    type: 'number',
    hideIn: {
      form: true,
    },
    sortable: true,
    align: 'left',
    tooltip:
      'module-equipment-electric-consumption-submodule-scientific-table-kg_co2eq',
  },
  {
    id: 't_co2eq',
    label: 't CO₂-eq',
    type: 'number',
    hideIn: {
      form: true,
      table: true,
    },
    sortable: true,
    align: 'left',
    tooltip:
      'module-equipment-electric-consumption-submodule-scientific-table-t_co2eq',
  },
];

const otherModuleFields: ModuleField[] = [
  {
    ...nameField,
    placeholder: `${MODULES.EquipmentElectricConsumption}.inputs.name-placeholder-other`,
    tooltip: 'module-equipment-electric-consumption-submodule-other-table-name',
  },
  ...baseModuleFields.slice(1),
];

// remove subclass field for IT equipment
const itmodulefields: ModuleField[] = [
  {
    ...nameField,
    placeholder: `${MODULES.EquipmentElectricConsumption}.inputs.name-placeholder-it`,
    tooltip: 'module-equipment-electric-consumption-submodule-it-table-name',
  },
  ...baseModuleFields.slice(1).filter((field) => field.id !== 'sub_class'),
];

export const equipmentElectricConsumption: ModuleConfig = {
  id: 'module_elec_001',
  type: MODULES.EquipmentElectricConsumption as Module,
  hasDescription: true,
  hasDescriptionSubtext: true,
  threshold: {
    type: MODULES_THRESHOLD_TYPES[0], // fixed threshold; configurable via backoffice later
    value: 100, // kg CO₂-eq; implicit coloring only
  },

  hasSubmodules: true,
  isCollapsible: true,
  uncertainty: 'high',
  totalFormatter: formatTonnesCO2,

  formStructure: 'perSubmodule',

  submodules: [
    {
      id: SUBMODULE_EQUIPMENT_TYPES.Scientific,
      type: SUBMODULE_EQUIPMENT_TYPES.Scientific as EquipmentElectricConsumptionSubType,
      // name: 'Scientific Equipment',
      tableNameKey:
        'equipment-electric-consumption-scientific-equipment-table-title',
      count: 4,
      moduleFields: baseModuleFields,
    },
    {
      id: SUBMODULE_EQUIPMENT_TYPES.IT,
      type: SUBMODULE_EQUIPMENT_TYPES.IT as EquipmentElectricConsumptionSubType,
      // name: 'IT Equipment',
      tableNameKey: 'equipment-electric-consumption-it-equipment-table-title',
      count: 4,
      moduleFields: itmodulefields,
    },
    {
      id: SUBMODULE_EQUIPMENT_TYPES.Other,
      type: SUBMODULE_EQUIPMENT_TYPES.Other as EquipmentElectricConsumptionSubType,
      // name: 'Other',
      tableNameKey:
        'equipment-electric-consumption-other-equipment-table-title',
      count: 4,
      moduleFields: otherModuleFields,
    },
  ],
  resultBigNumbers: [
    {
      titleKey: 'equipment-results-total-electricity-use',
      numberKey: 'total_electricity_use',
      comparisonKey: 'equipment-results-total-electricity-use-comparison',
      comparisonParams: { residents: "10'200" },
      comparisonHighlight: "10'200",
      color: 'negative',
      tooltipKey:
        'results-equipment-electric-consumption-stats-total-electricity-use-title',
    },
    {
      titleKey: 'equipment-results-share-of-lab-total',
      numberKey: 'share_of_lab_total',
      unitKey: 'equipment-results-share-of-lab-total-unit',
      comparisonKey: 'equipment-results-share-of-lab-total-comparison',
      comparisonParams: { percentage: '28%' },
      comparisonHighlight: '28%',
      color: 'negative',
      tooltipKey:
        'results-equipment-electric-consumption-stats-share-of-lab-total-title',
    },
    {
      titleKey: 'equipment-results-year-to-year-evolution',
      numberKey: 'year_to_year_evolution',
      comparisonKey: 'equipment-results-year-to-year-evolution-comparison',
      comparisonParams: { freezers: '3' },
      comparisonHighlight: '3 freezers',
      color: 'positive',
      tooltipKey:
        'results-equipment-electric-consumption-stats-year-to-year-evolution-title',
    },
  ],
};
