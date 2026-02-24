import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { formatTonnesCO2 } from 'src/utils/number';
import {
  SUBMODULE_PURCHASE_TYPES,
  MODULES,
  MODULES_THRESHOLD_TYPES,
} from 'src/constant/modules';
import type { PurchaseSubType } from 'src/constant/modules';
import type { Module } from 'src/constant/modules';

const purchaseFields: ModuleField[] = [
  {
    id: 'name',
    labelKey: `${MODULES.Purchase}.inputs.name`,
    type: 'text',
    required: true,
    placeholder: 'Enter value',
    sortable: true,
    align: 'left',
    ratio: '1/2',
  },
  {
    id: 'supplier',
    labelKey: `${MODULES.Purchase}.inputs.supplier`,
    type: 'text',
    required: true,
    placeholder: 'Enter value',
    sortable: true,
    align: 'left',
    ratio: '1/2',
  },
  {
    id: 'purchase_institutional_code',
    labelKey: `${MODULES.Purchase}.inputs.purchase_institutional_code`,
    optionsId: 'kind',
    type: 'select',
    required: true,
    sortable: true,
    align: 'left',
    // tooltip: 'Class can be edited via the Edit button only',
    inputTypeName: 'QSelect',
    readOnly: false,
    editableInline: true,
    ratio: '1/3',
    icon: 'o_category',
  },
  {
    id: 'quantity',
    labelKey: `${MODULES.Purchase}.inputs.quantity`,
    type: 'number',
    editableInline: true,
    min: 0,
    step: 1,
    ratio: '1/3',
    hideIn: { form: false },
    sortable: true,
  },
  {
    id: 'total_spent_amount',
    labelKey: `${MODULES.Purchase}.inputs.total_spent_amount`,
    type: 'number',
    editableInline: true,
    min: 0,
    step: 0.01,
    ratio: '1/3',
    hideIn: { form: false },
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

export const purchase: ModuleConfig = {
  id: 'module_purchase_001',
  type: MODULES.Purchase as Module,
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description:
    'Track purchases of scientific and IT equipment, and their associated emissions.',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  threshold: {
    type: MODULES_THRESHOLD_TYPES[0],
    value: 500, // kg CO₂-eq; implicit coloring only
  },
  numberFormatOptions: {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  },
  totalFormatter: formatTonnesCO2,
  submodules: [
    {
      id: SUBMODULE_PURCHASE_TYPES.ScientificEquipment,
      type: SUBMODULE_PURCHASE_TYPES.ScientificEquipment as PurchaseSubType,
      tableNameKey: `${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ScientificEquipment}-table-title`,
      moduleFields: purchaseFields,
    },
    {
      id: SUBMODULE_PURCHASE_TYPES.ITEquipment,
      type: SUBMODULE_PURCHASE_TYPES.ITEquipment as PurchaseSubType,
      tableNameKey: `${MODULES.Purchase}.${SUBMODULE_PURCHASE_TYPES.ITEquipment}-table-title`,
      moduleFields: purchaseFields,
    },
  ],
};
