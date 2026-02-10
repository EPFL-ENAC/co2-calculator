<template>
  <div>
    <div class="module-table-section__submodules">
      <template v-for="sub in currentModuleConfig.submodules" :key="sub.id">
        <sub-module-section
          :submodule="sub"
          :module-config="currentModuleConfig"
          :module-type="type"
          :disable="disable"
          :submodule-type="sub.type as any"
          :data="data"
          :loading="loading"
          :error="error"
          :unit-id="unitId"
          :year="year"
          :threshold="currentModuleConfig.threshold"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, Ref } from 'vue';
import { ModuleConfig } from 'src/constant/moduleConfig';
import { MODULES_CONFIG } from 'src/constant/module-config';
import SubModuleSection from 'src/components/organisms/module/SubModuleSection.vue';

import type { ModuleResponse } from 'src/constant/modules';

import { Module } from 'src/constant/modules';

const props = defineProps<{
  type: Module;
  data: ModuleResponse | null;
  loading: boolean;
  error: string | null;
  unitId: string;
  year: string | number;
  disable: boolean;
}>();

const currentModuleConfig: Ref<ModuleConfig> = computed(
  () => MODULES_CONFIG[props.type] as ModuleConfig,
);
</script>

<style scoped lang="scss">
.module-table-section__submodules {
  display: grid;
  grid-gap: 1rem;
}
</style>
