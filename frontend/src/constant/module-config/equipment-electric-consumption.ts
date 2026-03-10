import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { formatTonnesCO2 } from 'src/utils/number';
import type {
  Module,
  EquipmentElectricConsumptionSubType,
  AllSubmoduleTypes,
} from 'src/constant/modules';

import {
  MODULES,
  MODULES_THRESHOLD_TYPES,
  SUBMODULE_EQUIPMENT_TYPES,
} from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';

const moduleStore = useModuleStore();

const powerTooltip = `${MODULES.EquipmentElectricConsumption}.tooltips.power`;

const emissionTooltip = `${MODULES.EquipmentElectricConsumption}.tooltips.emission`;

/**
 * Get the factor values for a given combustion type from the taxonomy.
 * @param subModuleType
 * @param entry
 * @returns
 */
function getEquipmentValues(
  subModuleType: AllSubmoduleTypes,
  entry: Record<string, unknown>,
) {
  if (!entry) return {};
  const taxoNode = moduleStore.state.taxonomySubmodule[subModuleType];
  if (!taxoNode || !taxoNode.children) return {};
  const equipmentNode = taxoNode.children.find(
    (child) => child.name === entry['equipment_class'],
  );
  if (!equipmentNode) return {};
  if (!equipmentNode.children) return equipmentNode.values || {};
  const subClassNode = equipmentNode.children.find(
    (child) => child.name === entry['sub_class'],
  );
  if (!subClassNode) return {};
  return subClassNode.values || {};
}

const baseModuleFields: ModuleField[] = [
  {
    id: 'name',
    label: 'Equipment Name',
    labelKey: `${MODULES.EquipmentElectricConsumption}.inputs.name`,
    type: 'text',
    required: true,
    placeholder: 'e.g., Agitator, Centrifuge',
    sortable: true,
    align: 'left',
    readOnly: false,
    ratio: '1/1',
  },
  {
    id: 'equipment_class',
    label: 'Class',
    type: 'select',
    required: true,
    sortable: true,
    align: 'left',
    // tooltip: 'Class can be edited via the Edit button only',
    inputTypeName: 'QSelect',
    readOnly: false,
    editableInline: true,
    ratio: '1/2',
    icon: 'o_category',
    optionsFunction: async (subModuleType, entry) => {
      if (!entry) return [];
      const taxoNode = moduleStore.state.taxonomySubmodule[subModuleType];
      if (!taxoNode || !taxoNode.children) return [];
      return taxoNode.children.map((child) => ({
        value: child.name,
        label: child.label,
      }));
    },
  },
  {
    id: 'sub_class',
    label: 'Sub-class',
    type: 'select',
    required: true,
    min: 0,
    sortable: true,
    align: 'left',
    editableInline: true,
    readOnly: false,
    ratio: '1/2',
    icon: 'o_category',
    optionsFunction: async (subModuleType, entry) => {
      if (!entry) return [];
      const taxoNode = moduleStore.state.taxonomySubmodule[subModuleType];
      if (!taxoNode || !taxoNode.children) return [];
      const equipmentClassNode = taxoNode.children.find(
        (child) => child.name === entry['equipment_class'],
      );
      if (!equipmentClassNode || !equipmentClassNode.children) return [];
      return equipmentClassNode.children.map((child) => ({
        value: child.name,
        label: child.label,
      }));
    },
    visible: (subModuleType, entry) => {
      if (!entry) return false;
      const taxoNode = moduleStore.state.taxonomySubmodule[subModuleType];
      if (!taxoNode || !taxoNode.children) return false;
      const equipmentClassNode = taxoNode.children.find(
        (child) => child.name === entry['equipment_class'],
      );
      return !!(equipmentClassNode && equipmentClassNode.children);
    },
  },
  {
    id: 'active_power_w',
    label: 'Active power',
    type: 'number',
    required: true,
    min: 0,
    unit: 'W',
    sortable: true,
    align: 'left',
    tooltip: powerTooltip,
    readOnly: true,
    ratio: '3/12',
    icon: 'o_electric_bolt',
    hideIn: {
      form: false,
    },
    maxColumnWidth: 150,
    default: async (subModuleType, entry) => {
      const values = getEquipmentValues(subModuleType, entry);
      return (values['active_power_w'] as number) ?? null;
    },
  },
  {
    id: 'standby_power_w',
    label: 'Standby Power',
    type: 'number',
    required: true,
    min: 0,
    unit: 'W',
    sortable: true,
    align: 'left',
    tooltip: powerTooltip,
    readOnly: true,
    hideIn: {
      form: false,
    },
    editableInline: false,
    ratio: '3/12',
    icon: 'o_electric_bolt',
    maxColumnWidth: 150,
    default: async (subModuleType, entry) => {
      const values = getEquipmentValues(subModuleType, entry);
      return (values['standby_power_w'] as number) ?? null;
    },
  },
  {
    id: 'active_usage_hours',
    label: 'Active usage',
    type: 'number',
    required: true,
    min: 0,
    unit: 'hrs/wk',
    sortable: true,
    align: 'left',
    inputTypeName: 'QInput',
    editableInline: true,
    ratio: '3/12',
    icon: 'o_donut_large',
  },
  {
    id: 'passive_usage_hours',
    label: 'Standby usage',
    type: 'number',
    required: true,
    min: 0,
    unit: 'hrs/wk',
    sortable: true,
    align: 'left',
    inputTypeName: 'QInput',
    editableInline: true,
    ratio: '3/12',
    icon: 'o_donut_large',
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
    tooltip: emissionTooltip,
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
    tooltip: emissionTooltip,
  },
];

// remove subclass field for equipment-electric-consumption module
const itmodulefields: ModuleField[] = baseModuleFields.filter(
  (field) => field.id !== 'sub_class',
);

export const equipmentElectricConsumption: ModuleConfig = {
  id: 'module_elec_001',
  type: MODULES.EquipmentElectricConsumption as Module,
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: false,
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
      moduleFields: baseModuleFields,
    },
  ],
  resultBigNumbers: [
    {
      titleKey: 'equipment-electric-consumption-results-total-electricity-use',
      numberKey: 'total_electricity_use',
      comparisonKey:
        'equipment-electric-consumption-results-total-electricity-use-comparison',
      comparisonParams: { residents: "10'200" },
      comparisonHighlight: "10'200",
      color: 'negative',
      tooltipKey:
        'equipment-electric-consumption-results-total-electricity-use-tooltip',
    },
    {
      titleKey: 'equipment-electric-consumption-results-share-of-lab-total',
      numberKey: 'share_of_lab_total',
      unitKey: 'equipment-electric-consumption-results-share-of-lab-total-unit',
      comparisonKey:
        'equipment-electric-consumption-results-share-of-lab-total-comparison',
      comparisonParams: { percentage: '28%' },
      comparisonHighlight: '28%',
      color: 'negative',
      tooltipKey:
        'equipment-electric-consumption-results-share-of-lab-total-tooltip',
    },
    {
      titleKey: 'equipment-electric-consumption-results-year-to-year-evolution',
      numberKey: 'year_to_year_evolution',
      comparisonKey:
        'equipment-electric-consumption-results-year-to-year-evolution-comparison',
      comparisonParams: { freezers: '3' },
      comparisonHighlight: '3 freezers',
      color: 'positive',
      tooltipKey:
        'equipment-electric-consumption-results-year-to-year-evolution-tooltip',
    },
  ],
};
