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
        <div class="col">
          {{ $t(submodule.tableNameKey, { count: submoduleCount || 0 }) }}
        </div>
        <q-icon
          v-if="hasTableTooltip"
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer q-mr-sm"
          :aria-label="
            $t(`${moduleType}-${submoduleType}-table-title-info-label`)
          "
        >
          <q-tooltip
            v-if="hasTableTooltip"
            anchor="center right"
            self="top right"
            class="u-tooltip"
          >
            {{ $t(`${moduleType}-${submoduleType}-table-title-info-tooltip`) }}
          </q-tooltip>
        </q-icon>
      </div>
    </template>
    <q-separator />
    <q-card-section class="q-pa-none">
      <div v-if="submodule.moduleFields" class="q-mx-lg q-my-xl">
        <module-table
          :module-fields="submodule.moduleFields"
          :unit-id="unitId"
          :year="year"
          :threshold="effectiveThreshold"
          :has-top-bar="submodule.hasTableTopBar"
          :module-type="moduleType"
          :submodule-type="submodule.id"
          :module-config="moduleConfig"
          :submodule-config="submodule"
          :disable="isTableDisabled"
        />
      </div>
      <q-separator />
      <div
        v-if="isInputDeactivated"
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
        <div v-if="showModuleForm" class="q-mx-lg">
          <module-form
            ref="formRef"
            :fields="submodule.moduleFields"
            :submodule-type="submodule.type"
            :module-type="moduleType"
            :item="item"
            :has-subtitle="submodule.hasFormSubtitle"
            :has-add-with-note="submodule.hasFormAddWithNote"
            :add-button-label-key="submodule.addButtonLabelKey"
            :has-tooltip="submodule.hasFormTooltip"
            :unit-id="unitId"
            :year="year"
            :form-defaults="formDefaults"
            @submit="submitForm"
          />
        </div>
        <div v-else-if="showViewOnlyBadge" class="q-mx-lg q-my-md">
          <q-badge color="warning" class="q-px-md q-py-sm">
            {{ $t('common_view_only') }}
          </q-badge>
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
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import { useAuthStore } from 'src/stores/auth';
import { PermissionAction } from 'src/constant/permissions';
import type {
  ModuleResponse,
  Threshold,
  ConditionalSubmoduleProps,
  EnumSubmoduleType,
  Module,
} from 'src/constant/modules';
import { enumSubmodule, MODULES_THRESHOLD_TYPES } from 'src/constant/modules';
import { useModuleStore, useTimelineStore } from 'src/stores/modules';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { INSTITUTIONAL_ID_LABEL } from 'src/constant/institutionalId';
import { Notify } from 'quasar';
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
  threshold: Threshold;
  disable: boolean;
};

type SubModuleSectionProps = ConditionalSubmoduleProps & CommonProps;

const yearConfigStore = useYearConfigStore();
const props = defineProps<SubModuleSectionProps>();
const authStore = useAuthStore();

const submoduleKey = computed(() => {
  return props.submodule.id;
});

const isInputDeactivated = computed(() => {
  const unifiedConfig = yearConfigStore.getModule(props.moduleType as Module);
  if (!unifiedConfig) return false;
  const subConfig = unifiedConfig.submodules[submoduleKey.value];
  return subConfig?.inputs_deactivated ?? false;
});

const isTableDisabled = computed(
  () => props.disable || isInputDeactivated.value,
);

const backendThreshold = computed<Threshold | null>(() => {
  const unifiedConfig = yearConfigStore.getModule(props.moduleType as Module);
  if (!unifiedConfig) return null;

  const subConfig = unifiedConfig.submodules[submoduleKey.value];
  if (subConfig?.threshold === null || subConfig.threshold === undefined) {
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

const isFormDisabled = computed(() => props.disable);

const submoduleCount = computed(
  () =>
    moduleStore.state.data?.data_entry_types_total_items?.[
      enumSubmodule[props.submodule.id as EnumSubmoduleType]
    ] || 0,
);

const item = computed(() => {
  if (props.moduleType === 'headcount' && props.submoduleType === 'student') {
    return moduleStore.state.dataSubmodule?.[props.submodule.id]?.items[0];
  }
  return null;
});
const { te, t } = useI18n();

const hasModuleForm = computed(() => {
  return (
    props.submodule.moduleFields &&
    props.submodule.moduleFields.filter((field) => !field.hideIn?.form).length >
      0
  );
});

const showModuleForm = computed(
  () => hasModuleForm.value && !isFormDisabled.value && canEdit.value,
);

const showViewOnlyBadge = computed(
  () => Boolean(props.submodule.moduleFields) && !isFormDisabled.value,
);

const hasTableTooltip = computed(() => {
  if (!props.submodule.type) return false;
  const tooltipKey = `${props.moduleType}-${props.submodule.type}-table-title-info-tooltip`;
  return te(tooltipKey);
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
    );
  } else {
    try {
      await moduleStore.postItem(
        props.moduleType,
        props.unitId,
        props.year,
        props.submoduleType,
        payload,
      );
      if (props.submodule.notifyInfoOnAddKey) {
        Notify.create({
          type: 'info',
          message: t(props.submodule.notifyInfoOnAddKey),
        });
      }
    } catch (err: unknown) {
      // Replace generic "user institutional id" in server error messages with
      // the institution-specific label (SCIPER for EPFL).
      const raw = err instanceof Error ? err.message : 'Unexpected error';
      const message =
        raw === 'DUPLICATE_INSTITUTIONAL_ID'
          ? t('headcount-member-error-duplicate-uid', {
              label: INSTITUTIONAL_ID_LABEL,
            })
          : raw.replace(/user institutional id/gi, INSTITUTIONAL_ID_LABEL);

      formRef.value?.setFieldError('user_institutional_id', message);
    }
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
