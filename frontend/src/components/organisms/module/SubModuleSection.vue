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
          :threshold="threshold"
          :has-top-bar="submodule.hasTableTopBar"
          :module-type="moduleType"
          :submodule-type="submodule.id"
          :module-config="moduleConfig"
          :submodule-config="submodule"
          :disable="disable"
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
          :has-tooltip="submodule.hasFormTooltip"
          :unit-id="unitId"
          :year="year"
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
import { hasPermission, getModulePermissionPath } from 'src/utils/permission';
import { PermissionAction } from 'src/constant/permissions';
import type {
  ModuleResponse,
  Threshold,
  ConditionalSubmoduleProps,
  EnumSubmoduleType,
} from 'src/constant/modules';
import { enumSubmodule } from 'src/constant/modules';
import { useModuleStore, useTimelineStore } from 'src/stores/modules';
import { INSTITUTIONAL_ID_LABEL } from 'src/constant/institutionalId';
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

const props = defineProps<SubModuleSectionProps>();

const authStore = useAuthStore();

// Permission check: can user edit this module?
const canEdit = computed(() => {
  const permissionPath = getModulePermissionPath(props.moduleType);
  if (!permissionPath) {
    // Module doesn't require permission, allow editing (backward compatibility)
    return true;
  }
  return hasPermission(
    authStore.user?.permissions,
    permissionPath,
    PermissionAction.EDIT,
  );
});

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
