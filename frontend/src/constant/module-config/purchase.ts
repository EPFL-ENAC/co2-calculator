import { ModuleConfig } from 'src/constant/moduleConfig';

export const purchase: ModuleConfig = {
  id: 'module_purchase_001',
  type: 'purchase',
  name: 'Purchase',
  description: 'Track purchased goods and materials',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  submodules: [
    {
      id: 'sub_goods',
      name: 'Goods',
      tableColumns: [
        { key: 'item', label: 'Item', type: 'text', sortable: true },
        { key: 'quantity', label: 'Quantity', type: 'number', sortable: true },
        { key: 'kgCO2eq', label: 'kg CO2-eq', type: 'number', sortable: true },
      ],
      formInputs: [
        {
          id: 'purchase_item',
          label: 'Item Name',
          type: 'text',
          required: true,
        },
      ],
    },
  ],
};
