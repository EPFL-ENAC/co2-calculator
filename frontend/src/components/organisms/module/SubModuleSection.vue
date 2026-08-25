<template>
  <q-expansion-item
    v-if="submodule.tableNameKey"
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
        <planner-submodule-budget
          v-if="carbonReportId !== undefined"
          class="q-mx-lg q-my-lg"
          :carbon-report-id="carbonReportId"
          :module-type-id="getModuleTypeId(moduleType)"
          :submodule="submodule.id"
          :name="submoduleName"
          :currency="grantBudgetCurrency"
          :saved="grantBudget"
          :disable="disable"
        />
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
</template>

<script setup lang="ts">
import {
  Submodule as ConfigSubmodule,
  ModuleConfig,
} from 'src/constant/moduleConfig';
import ModuleTable from 'src/components/organisms/module/ModuleTable.vue';
import ModuleForm from 'src/components/organisms/module/ModuleForm.vue';
import PlannerSubmoduleBudget from 'src/components/organisms/planner/PlannerSubmoduleBudget.vue';
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
import { enumSubmodule, MODULES_THRESHOLD_TYPES } from 'src/constant/modules';
import { getModuleTypeId } from 'src/constant/moduleStates';
import { useModuleStore, useTimelineStore } from 'src/stores/modules';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { INSTITUTIONAL_ID_LABEL } from 'src/constant/institutionalId';
import { submitCreateItem } from 'src/utils/submitCreateItem';
import { Notify } from 'quasar';
import {
  getSubmoduleIconColor,
  getSubmoduleLighterColor,
} from 'src/composables/useModuleIconColors';
import {
  canShowModuleForm,
  resolveExplorerFormDefaults,
  resolvePlannerFormDefaults,
} from 'src/utils/module-table-access';
import { submoduleTooltipKey, type TooltipScope } from 'src/utils/tooltipScope';
interface Option {
  label: string;
  value: string;
}
type FieldValue = string | number | boolean | null | Option;
const moduleStore = useModuleStore();
const timelineStore = useTimelineStore();

onMounted(() => {
  // The timeline store only ever holds the Calculator's report (#2000) — an
  // Explorer table has no validated state of its own, so fetching it here
  // would just be wasted, unused traffic.
  const needsFte = props.submodule.moduleFields?.some(
    (f) => f.defaultFrom === 'total_fte',
  );
  const carbonReportId = timelineStore.currentCarbonReportId;
  if (
    needsFte &&
    !props.isExplorer &&
    carbonReportId &&
    carbonReportId !== moduleStore.validatedTotalsCarbonReportId
  ) {
    moduleStore.getValidatedTotals(carbonReportId);
  }
});

const formDefaults = computed<Record<string, unknown> | undefined>(() => {
  const validatedTotals = moduleStore.state.validatedTotals;
  const fields = props.submodule.moduleFields ?? [];

  const defaults: Record<string, unknown> = resolvePlannerFormDefaults(
    fields,
    props.carbonReportId != null,
  );
  if (props.isExplorer) {
    // Explorer never shows the Calculator's validated FTE total (#2000).
    Object.assign(defaults, resolveExplorerFormDefaults(fields));
  } else if (validatedTotals) {
    for (const field of fields) {
      // A validated total of 0 means there's nothing to pre-fill — leave
      // the field empty rather than showing a misleading 0.
      if (field.defaultFrom === 'total_fte' && validatedTotals.total_fte) {
        defaults[field.id] = Math.round(validatedTotals.total_fte);
      }
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
const props = withDefaults(defineProps<SubModuleSectionProps>(), {
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
});
const authStore = useAuthStore();

const submoduleKey = computed(() => {
  return props.submodule.id;
});

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
</style>
