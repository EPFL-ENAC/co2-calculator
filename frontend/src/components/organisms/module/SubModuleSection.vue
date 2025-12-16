<template>
  <q-expansion-item
    v-if="submodule.tableNameKey"
    :label="
      $t(submodule.tableNameKey, {
        count: data?.submodules?.[submodule.id]?.count || 0,
      })
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
          :submodule-type="submoduleType as any"
          :unit-id="unitId"
          :year="year"
          :threshold="threshold"
          :has-top-bar="submodule.hasTableTopBar"
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

const rows = computed(() => {
  const items = props.data?.submodules?.[props.submodule.id]?.items ?? [];
  // ensure stable id for q-table row-key
  return (items as ModuleItem[]).map((it, i) => ({
    id: it.id ?? `${props.submodule.id}_${i}`,
    ...it,
  }));
});
</script>
