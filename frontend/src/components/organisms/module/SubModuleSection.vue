<template>
  <q-card class="q-mb-md">
    <q-card-section>
      <div v-if="submodule.tableColumns" class="q-mt-md">
        <module-table
          :columns="submodule.tableColumns"
          :rows="rows"
          :loading="loading"
          :error="error"
        />
      </div>

      <div v-if="submodule.formInputs" class="q-mt-md">
        <module-form :inputs="submodule.formInputs" />
      </div>
    </q-card-section>
  </q-card>
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
