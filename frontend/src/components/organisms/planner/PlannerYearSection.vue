<template>
  <q-card flat bordered>
    <q-expansion-item
      v-model="yearOpen"
      header-class="text-h5 text-weight-medium"
    >
      <template #header>
        <q-item-section>
          {{
            yearData.is_grant
              ? $t('planner_project_grant_title')
              : yearData.year
          }}
        </q-item-section>
      </template>

      <q-separator />
      <q-card-section>
        <div class="text-weight-medium q-mb-sm">
          {{ $t('planner_reference_year_label') }}
        </div>
        <!-- Set: the value reads first, the action stays quiet beside it.
             Unset: nothing to read yet, so the action carries the label. -->
        <div
          v-if="yearData.reference_year"
          class="reference-year-box reference-year-row row items-center no-wrap"
        >
          <q-icon
            name="o_calendar_month"
            color="info"
            class="reference-year-row__icon"
          />
          <span class="reference-year-row__value text-weight-medium">
            {{ yearData.reference_year }}
          </span>
          <q-separator vertical class="reference-year-row__divider" />
          <q-btn
            :label="$t('planner_reference_year_change_link')"
            color="info"
            flat
            dense
            no-caps
            padding="none"
            class="reference-year-row__action text-weight-medium"
            :loading="settingReferenceYear"
            @click="referenceYearDialogOpen = true"
          />
        </div>
        <q-btn
          v-else
          color="info"
          flat
          no-caps
          align="left"
          class="reference-year-box reference-year-empty text-weight-medium"
          :loading="settingReferenceYear"
          @click="referenceYearDialogOpen = true"
        >
          <q-icon name="o_calendar_month" class="reference-year-row__icon" />
          <span>{{ $t('planner_reference_year_set_button') }}</span>
        </q-btn>
        <div class="text-body2 text-grey-7 q-mt-sm">
          {{
            yearData.reference_year
              ? $t('planner_reference_year_rebuild_hint')
              : $t('planner_reference_year_hint', { year: factorYear })
          }}
        </div>
      </q-card-section>

      <q-separator />

      <!-- Grant budget: the total lives here, its distribution lives inside
           each module; the check line reconciles the two (#1978). -->
      <template v-if="yearData.is_grant">
        <q-card-section>
          <div class="text-weight-medium q-mb-sm">
            {{ $t('planner_grant_budget_label') }}
          </div>
          <div class="row items-start q-gutter-sm">
            <q-input
              v-model.number="budgetInput"
              class="grant-budget-input"
              type="number"
              outlined
              dense
              hide-bottom-space
              min="0"
              :label="$t('planner_grant_budget_input_label')"
              :loading="savingBudget"
              @blur="saveBudget"
              @keyup.enter="saveBudget"
            />
            <q-select
              v-model="budgetCurrencyInput"
              class="grant-budget-currency"
              :options="CURRENCY_OPTIONS"
              :label="$t('planner_budget_currency_label')"
              outlined
              dense
              hide-bottom-space
              emit-value
              map-options
              @update:model-value="saveBudget"
            />
          </div>
          <div
            class="text-body2 q-mt-sm"
            :class="
              overDistributed
                ? 'text-negative'
                : fullyDistributed
                  ? 'text-positive'
                  : 'text-grey-7'
            "
          >
            {{ budgetCheckText }}
          </div>
        </q-card-section>
        <q-separator />
      </template>

      <planner-reference-year-dialog
        v-if="referenceYearDialogOpen"
        :key="`ref-year-${yearData.reference_year}`"
        v-model="referenceYearDialogOpen"
        :year="yearData.year"
        :reference-year="yearData.reference_year"
        :options="referenceYearOptions"
        :loading="settingReferenceYear"
        @confirm="onReferenceYearChange"
      />

      <!-- Flat separator-joined list, in Calculator order — same as the Explorer -->
      <template
        v-for="(entry, entryIdx) in moduleEntries"
        :key="entry.config.module"
      >
        <q-separator v-if="entryIdx > 0" />
        <q-expansion-item
          :model-value="isExpanded(entry.config.module)"
          header-class="q-py-md"
          @update:model-value="
            (open: boolean) => onToggle(entry.config.module, open)
          "
        >
          <template #header>
            <q-item-section>
              <div class="flex items-center">
                <module-icon-box
                  :name="entry.config.module"
                  size="sm"
                  class="q-mr-sm"
                />
                <div class="text-h5 text-weight-medium">
                  {{ $t(entry.config.module) }}
                </div>
              </div>
            </q-item-section>
            <q-item-section side @click.stop>
              <div class="row items-center no-wrap q-gutter-sm">
                <q-checkbox
                  :model-value="entry.module?.is_active ?? true"
                  :label="$t('planner_module_active_label')"
                  color="info"
                  size="sm"
                  dense
                  :disable="
                    !entry.module ||
                    togglingModuleId === entry.module.id ||
                    isGrantLocked(entry.config.module)
                  "
                  @update:model-value="
                    (active: boolean) => onToggleActive(entry, active)
                  "
                >
                  <q-tooltip>{{
                    isGrantLocked(entry.config.module)
                      ? $t('planner_module_grant_locked_tooltip')
                      : $t('planner_module_active_tooltip')
                  }}</q-tooltip>
                </q-checkbox>
              </div>
            </q-item-section>
          </template>

          <q-separator />
          <!-- Grid stripes run edge to edge, so they carry no padding. -->
          <div
            v-if="isExpanded(entry.config.module)"
            :class="isEdgeToEdge(entry.config.module) ? undefined : 'q-pa-md'"
          >
            <!-- Headcount and Purchases are single grids, so they carry one
                 submodule-budget field here; table modules get theirs inside
                 each submodule section (#1978). -->
            <template
              v-if="
                yearData.is_grant &&
                entry.module &&
                isGridModule(entry.config.module)
              "
            >
              <div class="q-pa-md">
                <div class="text-weight-medium q-mb-sm">
                  {{ $t('planner_budget_section_title') }}
                </div>
                <q-input
                  v-model.number="gridBudgetInputs[entry.config.module]"
                  class="grant-budget-input"
                  type="number"
                  outlined
                  dense
                  hide-bottom-space
                  min="0"
                  :suffix="currencyLabel(yearData.budget_currency)"
                  :label="
                    $t('planner_submodule_budget_label', {
                      submodule: $t(entry.config.module),
                    })
                  "
                  :loading="savingGridBudgetModule === entry.config.module"
                  :disable="entry.module.is_active === false"
                  @blur="saveGridBudget(entry)"
                  @keyup.enter="saveGridBudget(entry)"
                />
                <div class="text-body2 text-grey-7 q-mt-sm">
                  {{ $t('planner_submodule_budget_hint') }}
                </div>
              </div>
              <q-separator />
            </template>
            <!-- Headcount is a fixed SIUS-category grid and Purchases a
                   global-budget XOR per-category grid, not add-row tables
                   (design). Other modules reuse the Calculator tables. -->
            <template v-if="entry.config.module === MODULES.Headcount">
              <p class="text-body2 text-grey-7 q-px-md q-pt-md q-mb-md">
                {{ $t('simulation_headcount_fte_hint') }}
              </p>
              <planner-headcount-rows
                :carbon-report-id="yearData.id"
                :disable="entry.module?.is_active === false"
              />
            </template>
            <planner-purchase-rows
              v-else-if="entry.config.module === MODULES.Purchase"
              :key="factorScopedKey(entry.config.module)"
              :carbon-report-id="yearData.id"
              :project-years-count="grantYearsCountFor(entry.config.module)"
              :disable="entry.module?.is_active === false"
            />
            <!-- Grant proposals plan RF use from the reference year's whole
                 platform list; year sections keep the standard prefilled
                 table (#1980). -->
            <planner-research-facility-rows
              v-else-if="isGrantRfModule(entry.config.module)"
              :carbon-report-id="yearData.id"
              :project-years-count="projectYearsCount ?? null"
              :grant-budgets="entry.module?.budgets ?? null"
              :budget-currency="yearData.budget_currency"
              :disable="entry.module?.is_active === false"
            />
            <module-table-section
              v-else
              :key="factorScopedKey(entry.config.module)"
              :type="entry.config.module"
              :config-override="getPlannerModuleConfig(entry.config.module)"
              :data="moduleStore.state.data"
              :loading="moduleStore.state.loading"
              :error="moduleStore.state.error"
              :unit-id="unitId"
              :year="yearData.year"
              :factor-year="factorYear"
              :carbon-report-id="yearData.id"
              :show-reference-columns="
                entry.config.behavior === 'prefilled' && hasReferenceYear
              "
              :project-years-count="grantYearsCountFor(entry.config.module)"
              :show-grant-budgets="yearData.is_grant"
              :grant-budgets="entry.module?.budgets ?? null"
              :grant-budget-currency="yearData.budget_currency"
              :disable="entry.module?.is_active === false"
            />
          </div>
        </q-expansion-item>
      </template>
    </q-expansion-item>
  </q-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

import ModuleIconBox from 'src/components/atoms/ModuleIconBox.vue';
import ModuleTableSection from 'src/components/organisms/module/ModuleTableSection.vue';
import PlannerHeadcountRows from 'src/components/organisms/planner/PlannerHeadcountRows.vue';
import PlannerPurchaseRows from 'src/components/organisms/planner/PlannerPurchaseRows.vue';
import PlannerResearchFacilityRows from 'src/components/organisms/planner/PlannerResearchFacilityRows.vue';
import PlannerReferenceYearDialog from 'src/components/organisms/planner/PlannerReferenceYearDialog.vue';
import { CURRENCY_OPTIONS, currencyLabel } from 'src/constant/currencies';
import {
  PLANNER_MODULES,
  type PlannerModuleConfig,
} from 'src/constant/planner-module-config';
import { getPlannerModuleConfig } from 'src/constant/planner-module-config/module-configs';
import { getModuleTypeId } from 'src/constant/moduleStates';
import { MODULES, type Module } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { factorMountKey } from 'src/utils/factor-year';
import {
  useSimulatorPlansStore,
  type SimulatorPlanModule,
  type SimulatorPlanYear,
} from 'src/stores/simulatorPlans';

interface ModuleEntry {
  config: PlannerModuleConfig;
  module: SimulatorPlanModule | undefined;
}

const props = defineProps<{
  planId: number;
  yearData: SimulatorPlanYear;
  unitId: number;
  /** Latest Calculator report year of the unit (factor fallback). */
  defaultFactorYear: number | null;
  referenceYearOptions: { label: string; value: number }[];
  /** `${year}-${module}` of every expanded module across the page. */
  expandedKeys: string[];
  /** The plan's year count (end - start + 1); null until the range is set. */
  projectYearsCount?: number | null;
}>();
const emit = defineEmits<{
  toggleModule: [payload: { key: string; module: Module; open: boolean }];
}>();

const $q = useQuasar();
const { t, n } = useI18n();
const moduleStore = useModuleStore();
const plansStore = useSimulatorPlansStore();

const yearOpen = ref(true);
const settingReferenceYear = ref(false);
const referenceYearDialogOpen = ref(false);
const togglingModuleId = ref<number | null>(null);

// The reference year only gates the prefill columns; data entry itself is
// always open. Its rows and dropdowns follow `factorYear` below.
// Grant budget inputs are seeded from the loaded report once; the check line
// below reads the persisted store values, so it only moves on save (#1978).
const budgetInput = ref<number | null>(props.yearData.budget);
const budgetCurrencyInput = ref<string | null>(props.yearData.budget_currency);
const savingBudget = ref(false);
// Headcount and Purchases are single grids: their one budget field lives on
// this level, stored under the module name as the submodule key.
const gridBudgetInputs = ref<Record<string, number | null>>(
  Object.fromEntries(
    PLANNER_MODULES.map((config) => {
      const module = props.yearData.modules.find(
        (m) => m.module_type_id === getModuleTypeId(config.module),
      );
      return [config.module, module?.budgets?.[config.module] ?? null];
    }),
  ),
);
const savingGridBudgetModule = ref<string | null>(null);

const distributedBudget = computed(() =>
  props.yearData.modules.reduce(
    (sum, m) =>
      sum + Object.values(m.budgets ?? {}).reduce((s, value) => s + value, 0),
    0,
  ),
);

const overDistributed = computed(
  () =>
    props.yearData.budget !== null &&
    distributedBudget.value > props.yearData.budget,
);

const fullyDistributed = computed(
  () =>
    props.yearData.budget !== null &&
    distributedBudget.value === props.yearData.budget,
);

const budgetCheckText = computed(() => {
  const total = props.yearData.budget;
  if (total === null) return t('planner_grant_budget_hint');
  if (overDistributed.value) {
    return t('planner_grant_budget_over', {
      amount: n(distributedBudget.value - total),
    });
  }
  return t('planner_grant_budget_distribution', {
    distributed: n(distributedBudget.value),
    currency: currencyLabel(props.yearData.budget_currency),
    total: n(total),
    remaining: n(total - distributedBudget.value),
  });
});

function toBudgetValue(raw: number | null | undefined): number | null {
  return typeof raw === 'number' && Number.isFinite(raw) && raw >= 0
    ? raw
    : null;
}

async function saveBudget() {
  const value = toBudgetValue(budgetInput.value);
  const currency = budgetCurrencyInput.value;
  if (
    (value === props.yearData.budget &&
      currency === props.yearData.budget_currency) ||
    savingBudget.value
  ) {
    return;
  }
  savingBudget.value = true;
  try {
    await plansStore.setGrantBudget(props.yearData.id, value, currency);
  } catch {
    $q.notify({ type: 'negative', message: t('planner_grant_budget_error') });
  } finally {
    savingBudget.value = false;
  }
}

async function saveGridBudget(entry: ModuleEntry) {
  if (!entry.module) return;
  const submodule = entry.config.module;
  const value = toBudgetValue(gridBudgetInputs.value[submodule]);
  if (value === (entry.module.budgets?.[submodule] ?? null)) return;
  savingGridBudgetModule.value = submodule;
  try {
    await plansStore.setSubmoduleBudget(
      props.yearData.id,
      entry.module.module_type_id,
      submodule,
      value,
    );
  } catch {
    $q.notify({ type: 'negative', message: t('planner_grant_budget_error') });
  } finally {
    savingGridBudgetModule.value = null;
  }
}
const hasReferenceYear = computed(() => props.yearData.reference_year !== null);

// Factor year, mirroring the backend chain (`resolve_factor_year`): the
// reference year wins, then the unit's latest Calculator report year, then
// the plan year itself (units without any Calculator report).
const factorYear = computed(
  () =>
    props.yearData.reference_year ??
    props.defaultFactorYear ??
    props.yearData.year,
);

const GRID_MODULES: Module[] = [MODULES.Headcount, MODULES.Purchase];

function isGridModule(module: Module): boolean {
  return GRID_MODULES.includes(module);
}

/** Grant proposals swap the RF table for the platform-selection grid (#1980). */
function isGrantRfModule(module: Module): boolean {
  return props.yearData.is_grant && module === MODULES.ResearchFacilities;
}

/** Grid stripes run edge to edge, so these blocks carry no outer padding. */
function isEdgeToEdge(module: Module): boolean {
  return isGridModule(module) || isGrantRfModule(module);
}

// A grant proposal is first and foremost about the equipment it funds, so it
// always counts (#1976); research facilities left the set with their opt-in
// platform grid (#1980). Mirrors the backend GRANT_LOCKED_MODULE_TYPES set,
// which rejects the toggle server-side.
const GRANT_LOCKED_MODULES: Module[] = [MODULES.Equipment];

function isGrantLocked(module: Module): boolean {
  return props.yearData.is_grant && GRANT_LOCKED_MODULES.includes(module);
}

/**
 * Grant tables show kgCO₂eq per year and multiplied over the project's years
 * (#1979). Year sections never do, and grant-locked Equipment waits for its
 * custom grant UI (#1981); the RF grid shows the pair on its own rows.
 */
function grantYearsCountFor(module: Module): number | null {
  if (!props.yearData.is_grant || isGrantLocked(module)) return null;
  return props.projectYearsCount ?? null;
}

const moduleEntries = computed<ModuleEntry[]>(() =>
  PLANNER_MODULES.map((config) => ({
    config,
    module: props.yearData.modules.find(
      (m) => m.module_type_id === getModuleTypeId(config.module),
    ),
  })),
);

// The Project Grant report shares its year with the start-year report, so
// its expansion keys carry their own prefix.
const sectionKey = computed(() =>
  props.yearData.is_grant ? 'grant' : String(props.yearData.year),
);

function expansionKey(module: Module): string {
  return `${sectionKey.value}-${module}`;
}

function isExpanded(module: Module): boolean {
  return props.expandedKeys.includes(expansionKey(module));
}

function factorScopedKey(module: Module): string {
  return factorMountKey(module, factorYear.value);
}

async function refreshExpandedModule(module: Module) {
  await moduleStore.getModuleTotals(
    module,
    props.unitId,
    String(props.yearData.year),
    props.yearData.id,
  );
}

function onToggle(module: Module, open: boolean) {
  emit('toggleModule', { key: expansionKey(module), module, open });
  if (open) void refreshExpandedModule(module);
}

async function onReferenceYearChange(referenceYear: number | null) {
  settingReferenceYear.value = true;
  try {
    await plansStore.setReferenceYear(
      props.planId,
      props.yearData.year,
      referenceYear,
      props.yearData.is_grant,
    );
    referenceYearDialogOpen.value = false;
    // The prefilled modules were rebuilt from the new baseline; refresh this
    // section's open modules so their rows appear without a manual reload.
    const prefix = `${sectionKey.value}-`;
    for (const key of props.expandedKeys) {
      if (!key.startsWith(prefix)) continue;
      await refreshExpandedModule(key.slice(prefix.length) as Module);
    }
  } catch {
    $q.notify({ type: 'negative', message: t('planner_reference_year_error') });
  } finally {
    settingReferenceYear.value = false;
  }
}

async function onToggleActive(entry: ModuleEntry, active: boolean) {
  if (!entry.module) return;
  togglingModuleId.value = entry.module.id;
  try {
    await plansStore.setModuleActive(
      props.yearData.id,
      entry.module.module_type_id,
      active,
    );
  } finally {
    togglingModuleId.value = null;
  }
}
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

// Both states share one box so the set and unset slots stay the same size.
// q-btn brings its own min-height / line-height; drop both so the padding
// tokens alone decide the box, as they already do for the filled row.
.reference-year-box {
  display: inline-flex;
  gap: tokens.$reference-year-row-gap;
  padding: tokens.$reference-year-row-padding-y
    tokens.$reference-year-row-padding-x;
  border-width: tokens.$reference-year-row-border-weight;
  border-radius: tokens.$reference-year-row-border-radius;
  font-size: tokens.$reference-year-row-value-font-size;
  min-height: 0;
  line-height: 1;

  .reference-year-row__icon {
    font-size: tokens.$reference-year-row-icon-size;
  }

  :deep(.q-btn__content) {
    gap: tokens.$reference-year-row-gap;
    line-height: 1;
  }
}

// Setting row: the current value reads as the content, the action sits quietly
// beside it — changing the baseline is deliberate, not a stray click.
.reference-year-row {
  border-style: solid;
  border-color: tokens.$reference-year-row-border-color;

  &__value {
    line-height: 1;
  }

  &__divider {
    height: tokens.$reference-year-row-divider-height;
    align-self: center;
  }

  &__action {
    font-size: tokens.$reference-year-row-action-font-size;
  }
}

// The same slot before it holds anything: dashed, so it reads as waiting to be
// filled rather than as a call to action competing with the module list.
.reference-year-empty {
  border-style: tokens.$reference-year-row-empty-border-style;
  border-color: tokens.$reference-year-row-empty-border-color;
}

// Budget fields hold one amount; a bounded box keeps them from stretching
// across the card like a text field would.
.grant-budget-input {
  max-width: 240px;
  flex: 1;
}

.grant-budget-currency {
  width: 110px;
}
</style>
