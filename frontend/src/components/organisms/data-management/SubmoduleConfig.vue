<script setup lang="ts">
import { MODULE_SUBMODULES } from '@/constant/backoffice-module-config';
import SubmoduleItem from '@/components/molecules/data-management/SubmoduleItem.vue';

interface Props {
  module: string;
}

defineProps<Props>();
</script>

<template>
  <SubmoduleItem
    v-for="submodule in MODULE_SUBMODULES[module] ?? []"
    :key="submodule.key"
    :submodule="submodule"
  />
</template>

<style scoped></style>
