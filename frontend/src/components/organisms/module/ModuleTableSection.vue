<template>
  <div>
    <div
      v-if="currentModuleConfig.hasSubmodules && currentModuleConfig.submodules"
      class="module-table-section__submodules"
    >
      <sub-module-section
        v-for="sub in currentModuleConfig.submodules"
        :key="sub.id"
        :submodule="sub"
        :module-type="type"
        :submodule-type="sub.id"
        :data="data"
        :loading="loading"
        :error="error"
        :unit-id="unitId"
        :year="year"
        :threshold="currentModuleConfig.threshold"
      />
    </div>
    <div v-else>
      <module-table
        :module-fields="currentModuleConfig.moduleFields"
        :rows="rootRows"
        :loading="loading"
        :error="error"
        :module-type="type"
        :unit-id="unitId"
        :year="year"
        :threshold="currentModuleConfig.threshold"
      />
      <module-form
        :fields="currentModuleConfig.moduleFields"
        :submodule-type="'other'"
        :module-type="type"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, Ref } from 'vue';
import { ModuleConfig } from 'src/constant/moduleConfig';
import { MODULES_CONFIG } from 'src/constant/module-config';
import SubModuleSection from 'src/components/organisms/module/SubModuleSection.vue';
import ModuleTable from 'src/components/organisms/module/ModuleTable.vue';
import ModuleForm from 'src/components/organisms/module/ModuleForm.vue';
import type { ModuleResponse, ModuleItem } from 'src/constant/modules';

import { Module } from 'src/constant/modules';

const props = defineProps<{
  type: Module;
  data: ModuleResponse | null;
  loading: boolean;
  error: string | null;
  unitId: string;
  year: string | number;
}>();

const currentModuleConfig: Ref<ModuleConfig> = computed(
  () => MODULES_CONFIG[props.type] as ModuleConfig,
);

const rootRows = computed(() => {
  const items = (props.data?.submodules?.['default']?.items ??
    []) as ModuleItem[];
  return items.map((it, i) => ({ id: it.id ?? `row_${i}`, ...it }));
});
</script>

<style scoped lang="scss">
.module-table-section__submodules {
  display: grid;
  grid-gap: 1rem;
}
</style>
