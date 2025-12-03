<template>
  <q-expansion-item
    :label="submodule.name + ` (${rows.length})`"
    flat
    header-class="text-h5 text-weight-medium"
    class="q-mb-md container container--pa-none module-submodule-section q-mb-xl"
  >
    <q-separator />
    <q-card-section class="q-pa-none">
      <div v-if="submodule.tableColumns" class="q-mx-lg q-my-xl">
        <module-table
          :columns="submodule.tableColumns"
          :rows="rows"
          :loading="loading"
          :error="error"
          :form-inputs="submodule.formInputs"
        />
      </div>
      <q-separator />
      <div v-if="submodule.formInputs">
        <module-form :inputs="submodule.formInputs" />
      </div>
    </q-card-section>
  </q-expansion-item>
</template>

<script setup lang="ts">
import { Submodule as ConfigSubmodule } from 'src/constant/moduleConfig';
import ModuleTable from 'src/components/organisms/module/ModuleTable.vue';
import ModuleForm from 'src/components/organisms/module/ModuleForm.vue';
import { computed } from 'vue';
import type { ModuleResponse, ModuleItem } from 'src/constant/modules';

const props = defineProps<{
  submodule: ConfigSubmodule;
  loading?: boolean;
  error?: string | null;
  data?: ModuleResponse | null;
}>();

const rows = computed(() => {
  const items = props.data?.submodules?.[props.submodule.id]?.items ?? [];
  // ensure stable id for q-table row-key
  return (items as ModuleItem[]).map((it, i) => ({
    id: it.id ?? `${props.submodule.id}_${i}`,
    ...it,
  }));
});
</script>
