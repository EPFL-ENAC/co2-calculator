import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { SUBMODULE_PROCESSES_TYPES, MODULES } from 'src/constant/modules';
import type { ProcessesSubType, Module } from 'src/constant/modules';
import { formatTonnesCO2 } from 'src/utils/number';
const processEmissionsFields: ModuleField[] = [
  {
    id: 'emitted_gas',
    treeLevel: 0,
    labelKey: `${MODULES.ProcessEmissions}.inputs.emitted_gas`,
    type: 'select',
    required: true,
    sortable: true,
    editableInline: true,
    inputTypeName: 'QSelect',
    align: 'left',
    ratio: '1/3',
    hideIn: { form: false },
    icon: 'o_science',
  },
  {
    id: 'sub_category',
    treeLevel: 1,
    labelKey: `${MODULES.ProcessEmissions}.inputs.sub_category`,
    type: 'select',
    required: false,
    sortable: true,
    editableInline: true,
    inputTypeName: 'QSelect',
    align: 'left',
    ratio: '1/3',
    hideIn: { form: false },
    conditionalVisibility: {
      showWhen: {
        fieldId: 'emitted_gas',
        value: 'Refrigerants',
      },
    },
    icon: 'o_category',
  },
  {
    id: 'quantity_kg',
    labelKey: `${MODULES.ProcessEmissions}.inputs.quantity_kg`,
    type: 'number',
    required: true,
    editableInline: true,
    step: 0.001,
    ratio: '1/3',
    sortable: true,
    hideIn: { form: false },
    min: 0.001,
  },
  {
    id: 'kg_co2eq',
    labelKey: 'results_units_kg',
    type: 'number',
    readOnly: true,
    hideIn: { form: true },
    sortable: true,
  },
];

export const processEmissions: ModuleConfig = {
  id: 'module_processes_001',
  type: MODULES.ProcessEmissions as Module,
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description:
    'Estimate greenhouse gas emissions from chemical/physical reactions',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  numberFormatOptions: {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  },
  submodules: [
    {
      id: SUBMODULE_PROCESSES_TYPES.ProcessEmissions,
      type: SUBMODULE_PROCESSES_TYPES.ProcessEmissions as ProcessesSubType,
      tableNameKey: `${MODULES.ProcessEmissions}.table_title`,
      moduleFields: processEmissionsFields,
      hasTableAction: true,
      addButtonLabelKey: `${MODULES.ProcessEmissions}.add_button`,
    },
  ],
  totalFormatter: formatTonnesCO2,
};
