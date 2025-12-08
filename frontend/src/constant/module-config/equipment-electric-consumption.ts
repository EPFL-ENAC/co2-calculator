import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { MODULES, MODULES_THRESHOLD_TYPES } from '../modules';

const powerTooltip = `${MODULES.EquipmentElectricConsumption}.tooltips.power`;

const emissionTooltip = `${MODULES.EquipmentElectricConsumption}.tooltips.emission`;

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
    readOnly: true,
    ratio: '1/1',
  },
  {
    id: 'class',
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
  },
  {
    id: 'sub_class',
    label: 'Sub-class',
    type: 'select',
    required: true,
    min: 0,
    sortable: true,
    align: 'left',
    inputTypeName: 'QSelect',
    editableInline: true,
    readOnly: false,
    ratio: '1/2',
    icon: 'o_category',
  },
  {
    id: 'act_usage',
    label: 'Active Usage',
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
    id: 'pas_usage',
    label: 'Standby Usage',
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
    id: 'act_power',
    label: 'Active Power',
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
  },
  {
    id: 'pas_power',
    label: 'Standby Power',
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
  },
  {
    id: 'kg_co2eq',
    label: 'kg CO₂-eq',
    type: 'number',
    hideIn: {
      form: true,
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
  type: 'equipment-electric-consumption',
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

  formStructure: 'perSubmodule',
  submodules: [
    {
      id: 'sub_scientific',
      name: 'Scientific Equipment',
      count: 4,
      moduleFields: baseModuleFields,
    },
    {
      id: 'sub_it',
      name: 'IT Equipment',
      count: 4,
      moduleFields: itmodulefields,
    },
    {
      id: 'sub_other',
      name: 'Other',
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
