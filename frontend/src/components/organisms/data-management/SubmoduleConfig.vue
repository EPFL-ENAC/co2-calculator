<script setup lang="ts">
import { MODULE_SUBMODULES } from 'src/constant/backoffice-module-config';
import SubmoduleItem from 'src/components/molecules/data-management/SubmoduleItem.vue';

interface Props {
  module: string;
  selectedYear: number;
}

defineProps<Props>();
</script>

<template>
  <SubmoduleItem
    v-for="submodule in MODULE_SUBMODULES[module] ?? []"
    :key="submodule.key"
    :submodule="submodule"
    :selected-year="selectedYear"
  />
</template>

<style scoped></style>
