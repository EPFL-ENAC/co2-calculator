<template>
  <div>
    <!-- TODO: use i18n key instead-->
    <h2>{{ currentModuleConfig.name }}</h2>
    <p>{{ currentModuleConfig.description }}</p>
    <div
      v-if="currentModuleConfig.hasSubmodules && currentModuleConfig.submodules"
    >
      <sub-module-section
        v-for="sub in currentModuleConfig.submodules"
        :key="sub.id"
        :submodule="sub"
        :data="props.data"
        :loading="props.loading"
        :error="props.error"
      />
    </div>
    <div v-else>
      <module-table
        :columns="currentModuleConfig.tableColumns"
        :data="props.data"
        :loading="props.loading"
        :error="props.error"
      />
      <module-form :inputs="currentModuleConfig.formInputs" />
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
import type { ModuleResponse } from 'src/constant/modules';

import { Module } from 'src/constant/modules';

const props = defineProps<{
  type: Module;
  data: ModuleResponse | null;
  loading: boolean;
  error: string | null;
}>();

const currentModuleConfig: Ref<ModuleConfig> = computed(
  () => MODULES_CONFIG[props.type] as ModuleConfig,
);
</script>
