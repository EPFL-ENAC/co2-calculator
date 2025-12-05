<template>
  <q-expansion-item
    :label="
      submodule.name + ` (${data?.submodules?.[submodule.id]?.count || 0})`
    "
    flat
    header-class="text-h5 text-weight-medium"
    class="q-mb-md container container--pa-none module-submodule-section q-mb-xl"
  >
    <q-separator />
    <q-card-section class="q-pa-none">
      <div v-if="submodule.moduleFields" class="q-mx-lg q-my-xl">
        <module-table
          :module-fields="submodule.moduleFields"
          :rows="rows"
          :loading="loading"
          :error="error"
          :module-type="moduleType"
          :submodule-type="submoduleType"
          :unit-id="unitId"
          :year="year"
          :threshold="threshold"
        />
      </div>
      <q-separator />
      <div v-if="submodule.moduleFields">
        <module-form
          :fields="submodule.moduleFields"
          :submodule-type="submoduleType"
          :module-type="moduleType"
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
import type { ModuleResponse, ModuleItem, Module } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
interface Option {
  label: string;
  value: string;
}
type FieldValue = string | number | boolean | null | Option;
const moduleStore = useModuleStore();

const props = defineProps<{
  submodule: ConfigSubmodule;
  loading?: boolean;
  error?: string | null;
  data?: ModuleResponse | null;
  moduleType: Module;
  submoduleType: string; // for now use string to allow dynamic submodule types
  unitId: string;
  year: string | number;
  threshold?: import('src/constant/modules').Threshold;
}>();

const rows = computed(() => {
  const items = props.data?.submodules?.[props.submodule.id]?.items ?? [];
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
</script>
