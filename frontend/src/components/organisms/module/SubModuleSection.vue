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
      <div v-if="submodule.moduleFields && !disable && canEdit" class="q-mx-lg">
        <module-form
          :fields="submodule.moduleFields"
          :submodule-type="submodule.type"
          :module-type="moduleType"
          :item="item"
          :has-subtitle="submodule.hasFormSubtitle"
          :has-student-helper="submodule.hasStudentHelper"
          :has-add-with-note="submodule.hasFormAddWithNote"
          :add-button-label-key="submodule.addButtonLabelKey"
          :has-tooltip="submodule.hasFormTooltip"
          :unit-id="unitId"
          :year="year"
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
import { computed } from 'vue';
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
import { useModuleStore } from 'src/stores/modules';
interface Option {
  label: string;
  value: string;
}
type FieldValue = string | number | boolean | null | Option;
const moduleStore = useModuleStore();

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
const { te } = useI18n();

const hasTableTooltip = computed(() => {
  if (!props.submodule.type) return false;
  const tooltipKey = `${props.moduleType}-${props.submodule.type}-table-title-info-tooltip`;
  return te(tooltipKey);
});

// actions

function submitForm(payload: Record<string, FieldValue>) {
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
    moduleStore.postItem(
      props.moduleType,
      props.unitId,
      props.year,
      props.submoduleType,
      payload,
    );
  }
}
</script>
