import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { SUBMODULE_PROCESSES_TYPES, MODULES } from 'src/constant/modules';
import type { ProcessesSubType, Module } from 'src/constant/modules';

const processesFields: ModuleField[] = [
  {
    id: 'emitted_gas',
    optionsId: 'kind',
    labelKey: `${MODULES.Processes}.inputs.emitted_gas`,
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
    optionsId: 'subkind',
    labelKey: `${MODULES.Processes}.inputs.sub_category`,
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
    labelKey: `${MODULES.Processes}.inputs.quantity_kg`,
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
    label: 'kg CO₂-eq',
    type: 'number',
    readOnly: true,
    hideIn: { form: true },
    sortable: true,
  },
];

export const processes: ModuleConfig = {
  id: 'module_processes_001',
  type: MODULES.Processes as Module,
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
      id: SUBMODULE_PROCESSES_TYPES.ProcessEmission,
      type: SUBMODULE_PROCESSES_TYPES.ProcessEmission as ProcessesSubType,
      tableNameKey: `${MODULES.Processes}.table_title`,
      moduleFields: processesFields,
      hasTableAction: true,
      addButtonLabelKey: `${MODULES.Processes}.add_button`,
    },
  ],
};
