<template>
  <q-expansion-item
    v-if="submodule.tableNameKey && collapsible"
    v-model="moduleStore.state.expandedSubmodules[submodule.id]"
    flat
    header-class="text-h5 text-weight-medium"
    class="q-mb-md container container--pa-none module-submodule-section q-mb-xl"
  >
    <template #header>
      <div class="row flex items-center full-width">
        <div class="col row items-center no-wrap">
          <span>
            {{ $t(submodule.tableNameKey, { count: submoduleCount || 0 }) }}
          </span>
          <q-icon
            v-if="hasTableTooltip && inlineTooltip"
            :name="outlinedInfo"
            size="16px"
            color="grey-6"
            class="cursor-pointer q-ml-sm"
            :aria-label="$t('module-info-label')"
          >
            <q-tooltip anchor="center right" self="top right" class="u-tooltip">
              {{ $t(tableTooltipKey) }}
            </q-tooltip>
          </q-icon>
        </div>
        <q-icon
          v-if="hasTableTooltip && !inlineTooltip"
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer q-mr-sm"
          :aria-label="$t('module-info-label')"
        >
          <q-tooltip anchor="center right" self="top right" class="u-tooltip">
            {{ $t(tableTooltipKey) }}
          </q-tooltip>
        </q-icon>
      </div>
    </template>
    <q-separator />
    <q-card-section class="q-pa-none">
      <!-- The submodule's share of the grant budget, reconciled against the
           total in the Project Grant section header (#1978). -->
      <template v-if="showGrantBudget">
        <div class="q-mx-lg q-my-lg">
          <div class="text-weight-medium q-mb-sm">
            {{ $t('planner_budget_section_title') }}
          </div>
          <q-input
            v-model.number="grantBudgetInput"
            class="grant-budget-input"
            type="number"
            outlined
            dense
            hide-bottom-space
            min="0"
            :suffix="currencyLabel(grantBudgetCurrency)"
            :label="
              $t('planner_submodule_budget_label', {
                submodule: submoduleName,
              })
            "
            :loading="savingGrantBudget"
            :disable="disable"
            @blur="saveGrantBudget"
            @keyup.enter="saveGrantBudget"
          />
          <div class="text-body2 text-grey-7 q-mt-sm">
            {{ $t('planner_submodule_budget_hint') }}
          </div>
        </div>
        <q-separator />
      </template>
      <div v-if="submodule.moduleFields" class="q-mx-lg q-my-xl">
        <module-table
          :module-fields="submodule.moduleFields"
          :unit-id="unitId"
          :year="year"
          :factor-year="factorYear"
          :carbon-report-id="carbonReportId"
          :show-reference-columns="showReferenceColumns"
          :project-years-count="projectYearsCount"
          :percentage-locked="percentageLocked"
          :exclude-snapshots="excludeSnapshots"
          :threshold="effectiveThreshold"
          :has-top-bar="submodule.hasTableTopBar"
          :module-type="moduleType"
          :submodule-type="submodule.id"
          :module-config="moduleConfig"
          :submodule-config="submodule"
          :disable="isTableDisabled"
          :is-explorer="isExplorer"
          :module-color="submoduleColor"
          :module-color-lighter="submoduleLighterColor"
        />
      </div>
      <q-separator />
      <div
        v-if="isInputDeactivated && !isExplorer && !isPlanner"
        class="q-mx-lg q-my-md inputs-deactivated-notice"
      >
        <div class="inputs-deactivated-notice__content">
          <q-icon name="edit_off" size="sm" color="accent" class="q-mb-sm" />
          <div class="text-body2 text-weight-medium text-center text-primary">
            {{ $t('module_submodule_inputs_deactivated_notice') }}
          </div>
        </div>
      </div>
      <template v-else>
        <div v-if="showModuleForm">
          <module-form
            ref="formRef"
            :fields="submodule.moduleFields"
            :submodule-type="submodule.type"
            :module-type="moduleType"
            :item="item"
            :has-subtitle="submodule.hasFormSubtitle"
            :has-add-with-note="submodule.hasFormAddWithNote"
            :add-button-label-key="submodule.addButtonLabelKey"
            :unit-id="unitId"
            :year="year"
            :factor-year="factorYear"
            :form-defaults="formDefaults"
            :module-color="submoduleColor"
            @submit="submitForm"
          />
        </div>
      </template>
    </q-card-section>
  </q-expansion-item>

  <q-card
    v-else-if="submodule.tableNameKey"
    flat
    class="q-mb-md container container--pa-none module-submodule-section q-mb-xl"
  >
    <q-card-section>
      <div class="row flex items-center full-width">
        <div class="col row items-center no-wrap text-h5 text-weight-medium">
          <span>
            {{ $t(submodule.tableNameKey, { count: submoduleCount || 0 }) }}
          </span>
          <q-icon
            v-if="hasTableTooltip && inlineTooltip"
            :name="outlinedInfo"
            size="16px"
            color="grey-6"
            class="cursor-pointer q-ml-sm"
            :aria-label="$t('module-info-label')"
          >
            <q-tooltip anchor="center right" self="top right" class="u-tooltip">
              {{ $t(tableTooltipKey) }}
            </q-tooltip>
          </q-icon>
        </div>
        <q-icon
          v-if="hasTableTooltip && !inlineTooltip"
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer q-mr-sm"
          :aria-label="$t('module-info-label')"
        >
          <q-tooltip anchor="center right" self="top right" class="u-tooltip">
            {{ $t(tableTooltipKey) }}
          </q-tooltip>
        </q-icon>
      </div>
    </q-card-section>
    <q-separator />
    <q-card-section class="q-pa-none">
      <!-- The submodule's share of the grant budget, reconciled against the
           total in the Project Grant section header (#1978). -->
      <template v-if="showGrantBudget">
        <div class="q-mx-lg q-my-lg">
          <div class="text-weight-medium q-mb-sm">
            {{ $t('planner_budget_section_title') }}
          </div>
          <q-input
            v-model.number="grantBudgetInput"
            class="grant-budget-input"
            type="number"
            outlined
            dense
            hide-bottom-space
            min="0"
            :suffix="currencyLabel(grantBudgetCurrency)"
            :label="
              $t('planner_submodule_budget_label', {
                submodule: submoduleName,
              })
            "
            :loading="savingGrantBudget"
            :disable="disable"
            @blur="saveGrantBudget"
            @keyup.enter="saveGrantBudget"
          />
          <div class="text-body2 text-grey-7 q-mt-sm">
            {{ $t('planner_submodule_budget_hint') }}
          </div>
        </div>
        <q-separator />
      </template>
      <div v-if="submodule.moduleFields" class="q-mx-lg q-my-xl">
        <module-table
          :module-fields="submodule.moduleFields"
          :unit-id="unitId"
          :year="year"
          :factor-year="factorYear"
          :carbon-report-id="carbonReportId"
          :show-reference-columns="showReferenceColumns"
          :project-years-count="projectYearsCount"
          :percentage-locked="percentageLocked"
          :exclude-snapshots="excludeSnapshots"
          :threshold="effectiveThreshold"
          :has-top-bar="submodule.hasTableTopBar"
          :module-type="moduleType"
          :submodule-type="submodule.id"
          :module-config="moduleConfig"
          :submodule-config="submodule"
          :disable="disable"
          :is-explorer="isExplorer"
        />
      </div>
      <q-separator />
      <div v-if="hasModuleForm && !disable && canEdit" class="q-mx-lg">
        <module-form
          ref="formRef"
          :fields="submodule.moduleFields"
          :submodule-type="submodule.type"
          :module-type="moduleType"
          :item="item"
          :has-subtitle="submodule.hasFormSubtitle"
          :has-add-with-note="submodule.hasFormAddWithNote"
          :add-button-label-key="submodule.addButtonLabelKey"
          :unit-id="unitId"
          :year="year"
          :factor-year="factorYear"
          :form-defaults="formDefaults"
          @submit="submitForm"
        />
      </div>
      <div
        v-else-if="submodule.moduleFields && !disable && !canEdit"
        class="q-mx-lg q-my-md"
      >
        <q-badge color="warning" class="q-px-md q-py-sm">
          {{ $t('common_view_only') }}
        </q-badge>
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import {
  Submodule as ConfigSubmodule,
  ModuleConfig,
} from 'src/constant/moduleConfig';
import ModuleTable from 'src/components/organisms/module/ModuleTable.vue';
import ModuleForm from 'src/components/organisms/module/ModuleForm.vue';
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import { useAuthStore } from 'src/stores/auth';
import { PermissionAction } from 'src/stores/auth';
import type {
  ModuleResponse,
  Threshold,
  AllSubmoduleTypes,
  EnumSubmoduleType,
  Module,
} from 'src/constant/modules';
import { currencyLabel } from 'src/constant/currencies';
import { enumSubmodule, MODULES_THRESHOLD_TYPES } from 'src/constant/modules';
import { getModuleTypeId } from 'src/constant/moduleStates';
import { useModuleStore, useTimelineStore } from 'src/stores/modules';
import { useSimulatorPlansStore } from 'src/stores/simulatorPlans';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { INSTITUTIONAL_ID_LABEL } from 'src/constant/institutionalId';
import { submitCreateItem } from 'src/utils/submitCreateItem';
import { Notify } from 'quasar';
import {
  getSubmoduleIconColor,
  getSubmoduleLighterColor,
} from 'src/composables/useModuleIconColors';
import { canShowModuleForm } from 'src/utils/module-table-access';
import { submoduleTooltipKey, type TooltipScope } from 'src/utils/tooltipScope';
interface Option {
  label: string;
  value: string;
}
type FieldValue = string | number | boolean | null | Option;
const moduleStore = useModuleStore();
const timelineStore = useTimelineStore();

onMounted(() => {
  const needsFte = props.submodule.moduleFields?.some(
    (f) => f.defaultFrom === 'total_fte',
  );
  const carbonReportId = timelineStore.currentCarbonReportId;
  if (
    needsFte &&
    carbonReportId &&
    carbonReportId !== moduleStore.validatedTotalsCarbonReportId
  ) {
    moduleStore.getValidatedTotals(carbonReportId);
  }
});

const formDefaults = computed<Record<string, unknown> | undefined>(() => {
  const validatedTotals = moduleStore.state.validatedTotals;
  if (!validatedTotals) return undefined;

  const defaults: Record<string, unknown> = {};
  for (const field of props.submodule.moduleFields ?? []) {
    if (field.defaultFrom === 'total_fte') {
      defaults[field.id] = Math.round(validatedTotals.total_fte);
    }
  }
  return Object.keys(defaults).length > 0 ? defaults : undefined;
});

type CommonProps = {
  submodule: ConfigSubmodule;
  moduleConfig: ModuleConfig;
  loading?: boolean;
  error?: string | null;
  data?: ModuleResponse | null;
  unitId: number;
  year: string | number;
  /** Year whose factors the class/subclass options resolve against — see ModuleForm. */
  factorYear?: number | null;
  /** Plan-year report id; when set, module calls address it directly. */
  carbonReportId?: number;
  /** Planner prefilled: show the reference-kg column + % slider. */
  showReferenceColumns?: boolean;
  /** Planner Project Grant: plan year count for the "× project years" column. */
  projectYearsCount?: number | null;
  /** Grant equipment global mode: per-row % controls read-only (#1981). */
  percentageLocked?: boolean;
  /** Grant equipment global mode: list only manually added entries (#1981). */
  excludeSnapshots?: boolean;
  /** Planner Project Grant: show this submodule's budget field (#1978). */
  showGrantBudget?: boolean;
  /** The submodule's saved share of the grant budget. */
  grantBudget?: number | null;
  /** Currency code of the grant budget, shown as the field's suffix. */
  grantBudgetCurrency?: string | null;
  threshold: Threshold;
  disable: boolean;
  isExplorer?: boolean;
  /** Which space this section renders in; selects the tooltip text set. */
  tooltipScope?: TooltipScope;
};

type ModuleTypeProps = {
  moduleType: Module;
  submoduleType?: AllSubmoduleTypes;
};

type SubModuleSectionProps = ModuleTypeProps & CommonProps;

const yearConfigStore = useYearConfigStore();
const props = withDefaults(
  defineProps<SubModuleSectionProps & { collapsible?: boolean }>(),
  {
    collapsible: true,
    error: null,
    data: null,
    submoduleType: undefined,
    carbonReportId: undefined,
    factorYear: undefined,
    showReferenceColumns: undefined,
    projectYearsCount: null,
    percentageLocked: false,
    excludeSnapshots: false,
    showGrantBudget: false,
    grantBudget: null,
    grantBudgetCurrency: null,
    tooltipScope: 'calculator',
  },
);
const authStore = useAuthStore();

const submoduleKey = computed(() => {
  return props.submodule.id;
});

// Grant submodule budget (#1978): seeded from the saved value once; the
// Project Grant header's check line reads the store, so it moves on save.
const plansStore = useSimulatorPlansStore();

// The table titles embed a count ("Rooms ({count})"); translating with a
// plural count and stripping the parenthetical yields the bare name the
// budget label needs ("Rooms budget").
const submoduleName = computed(() =>
  props.submodule.tableNameKey
    ? t(props.submodule.tableNameKey, { count: 2 }).replace(
        /\s*\([^)]*\)\s*$/,
        '',
      )
    : '',
);
const grantBudgetInput = ref<number | null>(props.grantBudget);
const savingGrantBudget = ref(false);

async function saveGrantBudget() {
  if (props.carbonReportId === undefined || savingGrantBudget.value) return;
  const raw = grantBudgetInput.value;
  const value =
    typeof raw === 'number' && Number.isFinite(raw) && raw >= 0 ? raw : null;
  if (value === (props.grantBudget ?? null)) return;
  savingGrantBudget.value = true;
  try {
    await plansStore.setSubmoduleBudget(
      props.carbonReportId,
      getModuleTypeId(props.moduleType),
      props.submodule.id,
      value,
    );
  } catch {
    Notify.create({
      type: 'negative',
      message: t('planner_grant_budget_error'),
    });
  } finally {
    savingGrantBudget.value = false;
  }
}

const submoduleColor = computed(() =>
  getSubmoduleIconColor(props.submodule.id, props.moduleType),
);

const submoduleLighterColor = computed(
  () => `${getSubmoduleLighterColor(props.submodule.id, props.moduleType)}50`,
);

const isInputDeactivated = computed(() => {
  const unifiedConfig = yearConfigStore.getModule(props.moduleType as Module);
  if (!unifiedConfig) return false;
  const subConfig = unifiedConfig.submodules[submoduleKey.value];
  return subConfig?.inputs_deactivated ?? false;
});

// Planner tables address a plan-year report by id; the Calculator never does.
const isPlanner = computed(() => props.carbonReportId != null);

const isTableDisabled = computed(() => {
  if (props.isExplorer) return false;
  return props.disable || (!isPlanner.value && isInputDeactivated.value);
});

const backendThreshold = computed<Threshold | null>(() => {
  const unifiedConfig = yearConfigStore.getModule(props.moduleType as Module);
  if (!unifiedConfig) return null;

  // `== null` covers a missing subConfig too — planner submodules
  // (planner_headcount, ...) have no unified year-config entry.
  const subConfig = unifiedConfig.submodules[submoduleKey.value];
  if (subConfig?.threshold == null) {
    return null;
  }

  return {
    type: MODULES_THRESHOLD_TYPES[0],
    value: subConfig.threshold,
  };
});

const effectiveThreshold = computed<Threshold>(() => {
  return backendThreshold.value || props.threshold;
});

// Permission check: can user edit this module?
const canEdit = computed(() => {
  return authStore.hasUserModulePermission(
    props.moduleType,
    PermissionAction.EDIT,
  );
});

const submoduleCount = computed(() => {
  const submoduleEnumId =
    enumSubmodule[props.submodule.id as EnumSubmoduleType];

  // Preferred: lightweight per-module counts map (populated by prefetchAllModuleCounts).
  const fromTotalsMap =
    moduleStore.state.moduleTotalsMap[props.moduleType]?.[submoduleEnumId];
  if (typeof fromTotalsMap === 'number') return fromTotalsMap;

  // Fallback: shared module data slot (may belong to any currently-loaded module).
  const fromModuleTotals =
    moduleStore.state.data?.data_entry_types_total_items?.[submoduleEnumId];
  if (typeof fromModuleTotals === 'number') return fromModuleTotals;

  const fromSubmodule =
    moduleStore.state.dataSubmodule?.[props.submodule.id]?.summary?.total_items;
  if (typeof fromSubmodule === 'number') return fromSubmodule;

  const fromPagination =
    moduleStore.state.paginationSubmodule?.[props.submodule.id]?.rowsNumber;
  if (typeof fromPagination === 'number') return fromPagination;

  return 0;
});

const item = computed(() => {
  if (props.moduleType === 'headcount' && props.submoduleType === 'student') {
    return moduleStore.state.dataSubmodule?.[props.submodule.id]?.items[0];
  }
  return null;
});
const { t } = useI18n();

const hasModuleForm = computed(() => {
  return (
    props.submodule.moduleFields &&
    props.submodule.moduleFields.filter((field) => !field.hideIn?.form).length >
      0
  );
});

const showModuleForm = computed(
  () =>
    hasModuleForm.value &&
    canShowModuleForm({
      isExplorer: props.isExplorer === true,
      isPlanner: isPlanner.value,
      canEdit: canEdit.value,
      disable: props.disable,
    }),
);

const tableTooltipKey = computed(() =>
  submoduleTooltipKey(
    props.tooltipScope,
    props.moduleType,
    props.submodule.type ?? '',
  ),
);

// Planner and Explorer sit the icon right after the title, small and grey, to
// match their module headers; the Calculator keeps its right-aligned icon.
const inlineTooltip = computed(() => props.tooltipScope !== 'calculator');

const hasTableTooltip = computed(() => {
  if (!props.submodule.type) return false;
  return t(tableTooltipKey.value) !== '';
});

// actions

const formRef = ref<InstanceType<typeof ModuleForm> | null>(null);

async function submitForm(payload: Record<string, FieldValue>) {
  // if update! (for headcount student for instance)
  if (item.value && item.value.id) {
    return moduleStore.patchItem(
      props.moduleType,
      props.submoduleType,
      props.unitId,
      String(props.year),
      item.value.id,
      payload,
      props.carbonReportId,
    );
  } else {
    await submitCreateItem(
      (onCreated) =>
        moduleStore.postItem(
          props.moduleType,
          props.unitId,
          props.year,
          props.submoduleType,
          payload,
          onCreated,
          props.carbonReportId,
        ),
      {
        onCreated: () => {
          if (props.submodule.notifyInfoOnAddKey) {
            Notify.create({
              type: 'info',
              message: t(props.submodule.notifyInfoOnAddKey),
            });
          }
        },
        // The item was already created server-side; this failure comes from
        // an unrelated post-create refresh (totals/breakdown/state), not
        // from the submitted data — don't misattribute it to a form field.
        onRefreshFailed: () => {
          Notify.create({
            type: 'warning',
            message: t('common_post_create_refresh_error'),
          });
        },
        onCreateFailed: (err: unknown) => {
          // Replace generic "user institutional id" in server error messages
          // with the institution-specific label (SCIPER for EPFL).
          const raw = err instanceof Error ? err.message : 'Unexpected error';
          const message =
            raw === 'DUPLICATE_INSTITUTIONAL_ID'
              ? t('headcount-member-error-duplicate-uid', {
                  label: INSTITUTIONAL_ID_LABEL,
                })
              : raw.replace(/user institutional id/gi, INSTITUTIONAL_ID_LABEL);

          formRef.value?.setFieldError('user_institutional_id', message);
        },
      },
    );
  }
}
</script>

<style scoped>
.inputs-deactivated-notice {
  background-color: rgba(0, 0, 0, 0.02);
  border: 1px dashed rgba(0, 0, 0, 0.12);
  border-radius: 4px;
}

.inputs-deactivated-notice__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

/* A budget field holds one amount; a bounded box keeps it from stretching
   across the section like a text field would. */
.grant-budget-input {
  max-width: 240px;
}
</style>
