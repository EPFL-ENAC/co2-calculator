import type {
  ModuleConfig,
  ModuleField,
  Submodule,
} from 'src/constant/moduleConfig';
import { MODULES, type Module } from 'src/constant/modules';
import { MODULES_CONFIG } from 'src/constant/module-config';
import { PLANNER_MODULE_CONFIG } from 'src/constant/planner-module-config';

/**
 * ModuleConfig objects rendered inside the Simulator Plan by
 * ModuleTableSection.
 *
 * Purchases gets its own config (submodule CHF totals XOR one global
 * budget); the others reuse the Calculator config with two planner
 * adaptations applied by `withPlannerAdaptations`:
 * - no CSV top bar (bulk ingest pipelines are unit/year-scoped and would
 *   bypass the plan's report addressing)
 * - Travel's traveler dropdown offers categories instead of headcount names.
 *
 * Headcount is NOT here — it renders through PlannerHeadcountRows (fixed
 * SIUS-category grid), not a data table.
 */

const PURCHASE_CATEGORY_OPTIONS = [
  'scientific_equipment',
  'it_equipment',
  'consumable_accessories',
  'biological_chemical_gaseous_product',
  'services',
  'vehicles',
  'other_purchases',
].map((value) => ({ value, label: value }));

const plannerPurchaseFields: ModuleField[] = [
  {
    id: 'purchase_category',
    labelKey: 'planner_purchase_category_label',
    type: 'select',
    sortable: true,
    ratio: '1/2',
    // Reuses the Calculator purchase submodule titles as category labels.
    optionLabelKey: `${MODULES.Purchase}.{value}-table-title`,
    options: PURCHASE_CATEGORY_OPTIONS,
  },
  {
    id: 'amount_chf',
    labelKey: 'planner_purchase_amount_label',
    type: 'number',
    min: 0,
    sortable: true,
    ratio: '1/2',
    unit: 'CHF',
  },
];

const plannerPurchaseBudgetFields: ModuleField[] = [
  {
    id: 'amount_chf',
    labelKey: 'planner_purchase_amount_label',
    type: 'number',
    min: 0,
    sortable: true,
    ratio: '12/12',
    unit: 'CHF',
  },
];

const plannerPurchase: ModuleConfig = {
  id: 'planner_module_purchase',
  type: MODULES.Purchase as Module,
  hasDescription: false,
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  totalFormatter: (value) => String(value ?? ''),
  submodules: [
    {
      id: 'planner_purchase',
      type: 'planner_purchase',
      tableNameKey: 'planner_purchase_totals_table_title',
      hasTableTopBar: false,
      moduleFields: plannerPurchaseFields,
    },
    {
      id: 'planner_purchase_budget',
      type: 'planner_purchase_budget',
      tableNameKey: 'planner_purchase_budget_table_title',
      hasTableTopBar: false,
      moduleFields: plannerPurchaseBudgetFields,
    },
  ],
};

function plannerTravelerField(categories: string[]): Partial<ModuleField> {
  return {
    type: 'select',
    optionLabelKey: 'planner_traveler_category.{value}',
    options: categories.map((value) => ({ value, label: value })),
  };
}

/** Clone a Calculator config with the planner adaptations applied. */
function withPlannerAdaptations(module: Module): ModuleConfig {
  const base = MODULES_CONFIG[module] as ModuleConfig;
  const travelerCategories =
    PLANNER_MODULE_CONFIG[module]?.travelerCategories ?? null;
  const submodules: Submodule[] = (base.submodules ?? []).map((sub) => ({
    ...sub,
    hasTableTopBar: false,
    moduleFields: (sub.moduleFields ?? []).map((field) =>
      travelerCategories && field.type === 'headcount-member-select'
        ? { ...field, ...plannerTravelerField(travelerCategories) }
        : field,
    ),
  }));
  return { ...base, submodules };
}

const plannerConfigs: Partial<Record<Module, ModuleConfig>> = {
  [MODULES.Purchase]: plannerPurchase,
};

/** The ModuleConfig to render for a module inside the Simulator Plan. */
export function getPlannerModuleConfig(module: Module): ModuleConfig {
  return plannerConfigs[module] ?? withPlannerAdaptations(module);
}
