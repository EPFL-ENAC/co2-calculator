<template>
  <q-expansion-item
    v-if="submodule.tableNameKey"
    :label="
      $t(submodule.tableNameKey, {
        count: submoduleCount || 0,
      })
    "
    flat
    header-class="text-h5 text-weight-medium"
    class="q-mb-md container container--pa-none module-submodule-section q-mb-xl"
    @before-show="onExpand"
  >
    <q-separator />
    <q-card-section class="q-pa-none">
      <div v-if="submodule.moduleFields" class="q-mx-lg q-my-xl">
        <module-table
          :module-fields="submodule.moduleFields"
          :rows="rows"
          :loading="submoduleLoading"
          :error="submoduleError"
          :module-type="moduleType"
          :submodule-type="submoduleType as any"
          :unit-id="unitId"
          :year="year"
          :threshold="threshold"
          :has-top-bar="submodule.hasTableTopBar"
          :pagination-data="paginationData"
          :submodule-id="submodule.id"
          @page-change="onPageChange"
          @sort-change="onSortChange"
        />
      </div>
      <q-separator />
      <div v-if="submodule.moduleFields">
        <module-form
          :fields="submodule.moduleFields"
          :submodule-type="submoduleType"
          :module-type="moduleType"
          :has-subtitle="submodule.hasFormSubtitle"
          :has-student-helper="submodule.hasStudentHelper"
          :has-add-with-note="submodule.hasFormAddWithNote"
          :add-button-label-key="submodule.addButtonLabelKey"
          @submit="
            (payload: Record<string, FieldValue>) =>
              moduleStore.postItem(
                moduleType,
                unitId,
                year,
                submodule.id,
                payload,
              )
          "
        />
      </div>
    </q-card-section>
  </q-expansion-item>
</template>

<script setup lang="ts">
import { Submodule as ConfigSubmodule } from 'src/constant/moduleConfig';
import ModuleTable from 'src/components/organisms/module/ModuleTable.vue';
import ModuleForm from 'src/components/organisms/module/ModuleForm.vue';
import { computed } from 'vue';
import type {
  ModuleResponse,
  ModuleItem,
  Threshold,
  ConditionalSubmoduleProps,
} from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
interface Option {
  label: string;
  value: string;
}
type FieldValue = string | number | boolean | null | Option;
const moduleStore = useModuleStore();

type CommonProps = {
  submodule: ConfigSubmodule;
  loading?: boolean;
  error?: string | null;
  data?: ModuleResponse | null;
  unitId: string;
  year: string | number;
  threshold?: Threshold;
};

type SubModuleSectionProps = ConditionalSubmoduleProps & CommonProps;

const props = defineProps<SubModuleSectionProps>();

// Normalize submodule ID (remove 'sub_' prefix for store keys)
const normalizedSubmoduleId = computed(() => {
  return props.submodule.id.startsWith('sub_')
    ? props.submodule.id.replace('sub_', '')
    : props.submodule.id;
});

const submoduleData = computed(() => {
  return moduleStore.state.dataSubmodule[normalizedSubmoduleId.value] ?? null;
});

const submoduleLoading = computed(() => {
  return (
    moduleStore.state.loadingSubmodule[normalizedSubmoduleId.value] ?? false
  );
});

const submoduleError = computed(() => {
  return moduleStore.state.errorSubmodule[normalizedSubmoduleId.value] ?? null;
});

const submoduleCount = computed(() => {
  return (
    submoduleData.value?.count ??
    props.data?.submodules?.[props.submodule.id]?.count ??
    0
  );
});

const paginationData = computed(() => {
  return (
    moduleStore.state.paginationSubmodule[normalizedSubmoduleId.value] ?? null
  );
});

const rows = computed(() => {
  const items = submoduleData.value?.items ?? [];
  // ensure stable id for q-table row-key
  return (items as ModuleItem[]).map((it, i) => ({
    id: it.id ?? `${props.submodule.id}_${i}`,
    ...it,
  }));
});

const submoduleType = computed(() => {
  switch (props.submodule.id) {
    case 'sub_scientific':
      return 'scientific';
    case 'sub_it':
      return 'it';
    case 'sub_other':
      return 'other';
    default:
      return undefined as unknown as 'scientific' | 'it' | 'other' | undefined;
  }
});

function onExpand() {
  const isLoaded =
    moduleStore.state.loadedSubmodules[normalizedSubmoduleId.value];

  if (!isLoaded) {
    // Fetch submodule data with default pagination
    moduleStore.getSubmoduleData(
      props.moduleType,
      props.unitId,
      String(props.year),
      normalizedSubmoduleId.value,
      1, // page
      50, // limit
    );
  }
}

function onPageChange(page: number) {
  const pagination = paginationData.value;

  moduleStore.getSubmoduleData(
    props.moduleType,
    props.unitId,
    String(props.year),
    normalizedSubmoduleId.value,
    page,
    pagination?.limit ?? 50,
    pagination?.sortedBy,
    pagination?.sortOrder,
  );
}

function onSortChange(sortBy: string, sortOrder: string) {
  const pagination = paginationData.value;

  // Reset to page 1 when sorting changes
  moduleStore.getSubmoduleData(
    props.moduleType,
    props.unitId,
    String(props.year),
    normalizedSubmoduleId.value,
    1, // Reset to page 1
    pagination?.limit ?? 50,
    sortBy,
    sortOrder,
  );
}
</script>
