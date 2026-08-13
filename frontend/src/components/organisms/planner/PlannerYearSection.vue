<template>
  <q-card flat bordered>
    <q-expansion-item
      v-model="yearOpen"
      header-class="text-h5 text-weight-medium"
    >
      <template #header>
        <q-item-section>
          <div class="flex items-center">
            <span>
              {{
                yearData.is_grant
                  ? $t('planner_project_grant_title')
                  : yearData.year
              }}
            </span>
            <q-icon
              v-if="sectionTooltip"
              :name="outlinedInfo"
              size="16px"
              color="grey-6"
              class="cursor-pointer q-ml-sm"
              :aria-label="$t('module-info-label')"
              @click.stop
            >
              <q-tooltip
                anchor="center right"
                self="top right"
                class="u-tooltip"
              >
                {{ sectionTooltip }}
              </q-tooltip>
            </q-icon>
          </div>
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
                <q-icon
                  v-if="moduleTooltip(entry.config.module)"
                  :name="outlinedInfo"
                  size="16px"
                  color="grey-6"
                  class="cursor-pointer q-ml-sm"
                  :aria-label="$t('module-info-label')"
                  @click.stop
                >
                  <q-tooltip
                    anchor="center right"
                    self="top right"
                    class="u-tooltip"
                  >
                    {{ moduleTooltip(entry.config.module) }}
                  </q-tooltip>
                </q-icon>
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
                    !entry.module || togglingModuleId === entry.module.id
                  "
                  @update:model-value="
                    (active: boolean) => onToggleActive(entry, active)
                  "
                >
                  <q-tooltip>{{
                    $t('planner_module_active_tooltip')
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
                :key="factorScopedKey(entry.config.module)"
                :carbon-report-id="yearData.id"
                :disable="entry.module?.is_active === false"
              />
            </template>
            <planner-purchase-rows
              v-else-if="entry.config.module === MODULES.Purchase"
              :key="factorScopedKey(entry.config.module)"
              :carbon-report-id="yearData.id"
              :project-years-count="grantYearsCount"
              :disable="entry.module?.is_active === false"
            />
            <!-- Grant proposals plan RF use from the reference year's whole
                 platform list; year sections keep the standard prefilled
                 table (#1980). -->
            <planner-research-facility-rows
              v-else-if="isGrantRfModule(entry.config.module)"
              :key="factorScopedKey(entry.config.module)"
              :carbon-report-id="yearData.id"
              :factor-year="yearData.reference_year ?? yearData.year"
              :project-years-count="projectYearsCount ?? null"
              :grant-budgets="entry.module?.budgets ?? null"
              :budget-currency="yearData.budget_currency"
              :disable="entry.module?.is_active === false"
            />
            <template v-else>
              <!-- Grant equipment plans either line by line or with one
                   global percentage over all prefilled lines (#1981); adding
                   an equipment stays available in both modes. -->
              <div
                v-if="isGrantEquipmentModule(entry.config.module)"
                class="q-mb-lg"
              >
                <div class="text-weight-medium q-mb-sm">
                  {{ $t('planner_equipment_mode_title') }}
                </div>
                <div class="row items-center no-wrap">
                  <button
                    type="button"
                    class="planner-mode__label text-body1"
                    :class="
                      equipmentMode === 'per_line'
                        ? 'text-weight-medium'
                        : 'text-grey-6'
                    "
                    :aria-pressed="equipmentMode === 'per_line'"
                    :disabled="equipmentModeControlsDisabled(entry)"
                    @click="onEquipmentModeRequest('per_line')"
                  >
                    {{ $t('planner_equipment_mode_per_line') }}
                  </button>
                  <q-toggle
                    :model-value="equipmentMode === 'global'"
                    color="info"
                    keep-color
                    size="lg"
                    :disable="equipmentModeControlsDisabled(entry)"
                    @update:model-value="
                      (on: boolean) =>
                        onEquipmentModeRequest(on ? 'global' : 'per_line')
                    "
                  />
                  <button
                    type="button"
                    class="planner-mode__label text-body1"
                    :class="
                      equipmentMode === 'global'
                        ? 'text-weight-medium'
                        : 'text-grey-6'
                    "
                    :aria-pressed="equipmentMode === 'global'"
                    :disabled="equipmentModeControlsDisabled(entry)"
                    @click="onEquipmentModeRequest('global')"
                  >
                    {{ $t('planner_equipment_mode_global') }}
                  </button>
                </div>
                <div class="text-body2 text-grey-7 q-mt-xs">
                  {{
                    equipmentMode === 'global'
                      ? $t('planner_equipment_mode_global_hint')
                      : $t('planner_equipment_mode_per_line_hint')
                  }}
                </div>
                <!-- One budget for the whole module in global mode; the
                     per-submodule fields carry it in per-line mode (#1981). -->
                <template v-if="equipmentMode === 'global'">
                  <q-separator class="planner-equipment-separator q-my-md" />
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
                    :disable="entry.module?.is_active === false"
                    @blur="saveGridBudget(entry)"
                    @keyup.enter="saveGridBudget(entry)"
                  />
                  <div class="text-body2 text-grey-7 q-mt-sm">
                    {{ $t('planner_submodule_budget_hint') }}
                  </div>
                  <q-separator class="planner-equipment-separator q-my-md" />
                  <div
                    class="planner-equipment-global-row row items-center no-wrap"
                  >
                    <label
                      for="equipment-global-percentage"
                      class="col text-body2 text-weight-medium"
                    >
                      {{ $t('planner_equipment_mode_global') }}
                    </label>
                    <q-input
                      v-model.number="globalPercentage"
                      for="equipment-global-percentage"
                      class="planner-equipment-global-row__input"
                      type="number"
                      :min="0"
                      :max="100"
                      outlined
                      dense
                      hide-bottom-space
                      suffix="%"
                      :loading="applyingGlobalPercentage"
                      :disable="
                        entry.module?.is_active === false ||
                        switchingEquipmentMode
                      "
                      @blur="applyGlobalPercentage"
                      @keyup.enter="applyGlobalPercentage"
                    />
                  </div>
                </template>
                <q-dialog
                  v-model="equipmentSwitchDialogOpen"
                  :persistent="switchingEquipmentMode"
                >
                  <q-card style="min-width: 420px">
                    <q-card-section class="text-h4 text-weight-medium">
                      {{ $t('planner_purchase_switch_dialog_title') }}
                    </q-card-section>
                    <q-card-section class="text-body2 text-grey-8 q-pt-none">
                      {{ $t(equipmentSwitchMessageKey) }}
                    </q-card-section>
                    <q-card-actions class="q-px-md q-pb-md">
                      <q-btn
                        :label="$t('common_validate_short')"
                        :loading="switchingEquipmentMode"
                        color="info"
                        unelevated
                        no-caps
                        class="text-weight-medium"
                        @click="confirmEquipmentSwitch"
                      />
                      <q-btn
                        v-close-popup
                        :label="$t('common_cancel')"
                        :disable="switchingEquipmentMode"
                        color="primary"
                        unelevated
                        outline
                        no-caps
                        class="text-weight-medium"
                      />
                    </q-card-actions>
                  </q-card>
                </q-dialog>
              </div>
              <module-table-section
                :key="moduleMountKey(entry.config.module)"
                :type="entry.config.module"
                :config-override="
                  getPlannerModuleConfig(entry.config.module, selfTraveler)
                "
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
                :project-years-count="grantYearsCount"
                :percentage-locked="isGlobalEquipment(entry.config.module)"
                :show-grant-budgets="
                  yearData.is_grant && !isGlobalEquipment(entry.config.module)
                "
                :grant-budgets="entry.module?.budgets ?? null"
                :grant-budget-currency="yearData.budget_currency"
                :disable="entry.module?.is_active === false"
                :tooltip-scope="tooltipScope"
              />
            </template>
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
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import { moduleTooltipKey, type TooltipScope } from 'src/utils/tooltipScope';
import PlannerHeadcountRows from 'src/components/organisms/planner/PlannerHeadcountRows.vue';
import PlannerPurchaseRows from 'src/components/organisms/planner/PlannerPurchaseRows.vue';
import PlannerResearchFacilityRows from 'src/components/organisms/planner/PlannerResearchFacilityRows.vue';
import PlannerReferenceYearDialog from 'src/components/organisms/planner/PlannerReferenceYearDialog.vue';
import { CURRENCY_OPTIONS, currencyLabel } from 'src/constant/currencies';
import {
  PLANNER_MODULES,
  type PlannerModuleConfig,
} from 'src/constant/planner-module-config';
import {
  getPlannerModuleConfig,
  type PlannerSelfTraveler,
} from 'src/constant/planner-module-config/module-configs';
import { getModuleTypeId } from 'src/constant/moduleStates';
import {
  MODULES,
  SUBMODULE_EQUIPMENT_TYPES,
  type Module,
} from 'src/constant/modules';
import { useAuthStore } from 'src/stores/auth';
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
const authStore = useAuthStore();
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
      currency: currencyLabel(props.yearData.budget_currency),
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

/** Grant equipment gets the per-line / global percentage toggle (#1981). */
function isGrantEquipmentModule(module: Module): boolean {
  return props.yearData.is_grant && module === MODULES.Equipment;
}

// Grant equipment modes: per-line keeps the row sliders; global applies one
// percentage to every prefilled line at once (#1981). View state only, the
// entries are the same either way.
const equipmentMode = ref<'per_line' | 'global'>('per_line');
const globalPercentage = ref(0);
const appliedGlobalPercentage = ref<number | null>(null);
const applyingGlobalPercentage = ref(false);
// Bumped after a global apply: the table remounts and refetches its
// submodule rows, whose percentages all changed server-side.
const equipmentTableTick = ref(0);

const equipmentSwitchDialogOpen = ref(false);
const pendingEquipmentMode = ref<'per_line' | 'global' | null>(null);
const switchingEquipmentMode = ref(false);

const EQUIPMENT_PER_LINE_BUDGET_KEYS: string[] = Object.values(
  SUBMODULE_EQUIPMENT_TYPES,
);

const equipmentSwitchMessageKey = computed(() =>
  equipmentMode.value === 'per_line'
    ? 'planner_equipment_switch_to_global_message'
    : 'planner_equipment_switch_to_per_line_message',
);

function equipmentEntry(): ModuleEntry | undefined {
  return moduleEntries.value.find((e) => e.config.module === MODULES.Equipment);
}

function abandonedBudgetKeys(mode: 'per_line' | 'global'): string[] {
  return mode === 'per_line'
    ? EQUIPMENT_PER_LINE_BUDGET_KEYS
    : [MODULES.Equipment];
}

// The loaded table totals when they belong to this module, the plan-year
// stats otherwise (the module store slot is shared across expanded modules).
function equipmentTotalKg(entry: ModuleEntry): number {
  const data = moduleStore.state.data;
  if (
    entry.module &&
    data?.carbon_report_module_id === entry.module.id &&
    typeof data.totals?.total_kg_co2eq === 'number'
  ) {
    return data.totals.total_kg_co2eq;
  }
  const total = entry.module?.stats?.total;
  return typeof total === 'number' ? total : 0;
}

// Prefilled lines all at 0% produce no kg, so an untouched module switches
// silently; budgets of the mode being left count as data too.
function equipmentHasDataToLose(entry: ModuleEntry): boolean {
  const budgets = entry.module?.budgets ?? {};
  if (
    abandonedBudgetKeys(equipmentMode.value).some((key) => budgets[key] != null)
  ) {
    return true;
  }
  return equipmentTotalKg(entry) > 0;
}

function equipmentModeControlsDisabled(entry: ModuleEntry): boolean {
  return (
    switchingEquipmentMode.value ||
    applyingGlobalPercentage.value ||
    savingGridBudgetModule.value === MODULES.Equipment ||
    entry.module?.is_active === false
  );
}

function onEquipmentModeRequest(next: 'per_line' | 'global') {
  if (next === equipmentMode.value || switchingEquipmentMode.value) return;
  const entry = equipmentEntry();
  if (entry && equipmentHasDataToLose(entry)) {
    pendingEquipmentMode.value = next;
    equipmentSwitchDialogOpen.value = true;
    return;
  }
  equipmentMode.value = next;
  globalPercentage.value = 0;
  appliedGlobalPercentage.value = null;
}

async function confirmEquipmentSwitch() {
  const next = pendingEquipmentMode.value;
  const entry = equipmentEntry();
  if (next === null || !entry?.module) return;
  switchingEquipmentMode.value = true;
  try {
    await plansStore.setModuleReferencePercentage(
      props.yearData.id,
      entry.module.module_type_id,
      0,
    );
    const budgets = entry.module.budgets ?? {};
    for (const key of abandonedBudgetKeys(equipmentMode.value)) {
      if (budgets[key] == null) continue;
      await plansStore.setSubmoduleBudget(
        props.yearData.id,
        entry.module.module_type_id,
        key,
        null,
      );
    }
    if (equipmentMode.value === 'global') {
      gridBudgetInputs.value[MODULES.Equipment] = null;
    }
    equipmentMode.value = next;
    pendingEquipmentMode.value = null;
    equipmentSwitchDialogOpen.value = false;
    globalPercentage.value = 0;
    appliedGlobalPercentage.value = 0;
    await refreshExpandedModule(MODULES.Equipment);
    equipmentTableTick.value += 1;
  } catch {
    $q.notify({
      type: 'negative',
      message: t('planner_equipment_switch_error'),
    });
  } finally {
    switchingEquipmentMode.value = false;
  }
}

function isGlobalEquipment(module: Module): boolean {
  return isGrantEquipmentModule(module) && equipmentMode.value === 'global';
}

function moduleMountKey(module: Module): string {
  const base = factorScopedKey(module);
  return module === MODULES.Equipment
    ? `${base}-${equipmentTableTick.value}`
    : base;
}

async function applyGlobalPercentage() {
  const value = Math.min(100, Math.max(0, Number(globalPercentage.value)));
  if (!Number.isFinite(value)) return;
  globalPercentage.value = value;
  if (applyingGlobalPercentage.value || value === appliedGlobalPercentage.value)
    return;
  applyingGlobalPercentage.value = true;
  try {
    await plansStore.setModuleReferencePercentage(
      props.yearData.id,
      getModuleTypeId(MODULES.Equipment),
      value,
    );
    appliedGlobalPercentage.value = value;
    // The rows' percentages and kg changed; refresh totals and remount the
    // table so its rows refetch.
    await refreshExpandedModule(MODULES.Equipment);
    equipmentTableTick.value += 1;
  } catch {
    $q.notify({
      type: 'negative',
      message: t('planner_equipment_global_error'),
    });
  } finally {
    applyingGlobalPercentage.value = false;
  }
}

/** Grid stripes run edge to edge, so these blocks carry no outer padding. */
function isEdgeToEdge(module: Module): boolean {
  return isGridModule(module) || isGrantRfModule(module);
}

/**
 * Grant tables show kgCO₂eq per year and multiplied over the project's years
 * (#1979). Year sections never do; the RF grid shows the pair on its own rows.
 */
// The Grant section and the project-year sections carry their own guidance
// texts, so the tooltip set follows the section kind (tooltips.ts).
const tooltipScope = computed<TooltipScope>(() =>
  props.yearData.is_grant ? 'planner-grant' : 'planner-year',
);

const sectionTooltip = computed(() =>
  t(
    props.yearData.is_grant
      ? 'planner-grant-section-title'
      : 'planner-year-section-title',
  ),
);

function moduleTooltip(module: Module): string {
  return t(moduleTooltipKey(tooltipScope.value, module));
}

const grantYearsCount = computed<number | null>(() =>
  props.yearData.is_grant ? (props.projectYearsCount ?? null) : null,
);

// Grant sections open every module's input form to any unit member; the
// effective year sections follow the workspace module permissions, so a
// standard user only sees Travel and External Clouds & AI (#1983).
const visibleModules = computed<PlannerModuleConfig[]>(() =>
  PLANNER_MODULES.filter(
    (config) =>
      props.yearData.is_grant || authStore.canUserAccessModule(config.module),
  ),
);

const selfTraveler = computed<PlannerSelfTraveler | null>(() => {
  const institutionalId = authStore.user?.institutional_id;
  if (!institutionalId || authStore.hasUserCanValidateModuleStatus()) {
    return null;
  }
  return { institutional_id: institutionalId, name: authStore.displayName };
});

const moduleEntries = computed<ModuleEntry[]>(() =>
  visibleModules.value.map((config) => ({
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

// Both equipment modes are named on either side of the switch; the one not
// in use reads as unavailable rather than disappearing (purchase pattern).
.planner-mode__label {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  cursor: pointer;
}

.planner-equipment-global-row {
  &__input {
    width: tokens.$planner-grid-amount-input-width;

    :deep(.q-field__suffix) {
      font-size: tokens.$text-size-sm;
      color: tokens.$color-text-muted;
    }
  }
}

// The block sits in the q-pa-md module body; these bleed to its edges.
.planner-equipment-separator {
  margin-left: -16px;
  margin-right: -16px;
}

.grant-budget-currency {
  width: 110px;
}
</style>
