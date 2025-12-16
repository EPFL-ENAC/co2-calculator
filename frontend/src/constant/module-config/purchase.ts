import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { PurchaseSubType, SUBMODULE_PURCHASE_TYPES } from '../modules';

const goodsFields: ModuleField[] = [
  {
    id: 'item',
    label: 'Item',
    type: 'text',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'quantity',
    label: 'Quantity',
    type: 'number',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'kg_co2eq',
    label: 'kg CO₂-eq',
    type: 'number',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'purchase_item',
    label: 'Item Name',
    type: 'text',
    required: true,
    hideIn: { table: true },
  },
];

export const purchase: ModuleConfig = {
  id: 'module_purchase_001',
  type: 'purchase',
  name: 'Purchase',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  description: 'Track purchased goods and materials',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  submodules: [
    {
      id: 'sub_goods',
      type: SUBMODULE_PURCHASE_TYPES.Good as PurchaseSubType,
      name: 'Goods',
      moduleFields: goodsFields,
    },
  ],
};
