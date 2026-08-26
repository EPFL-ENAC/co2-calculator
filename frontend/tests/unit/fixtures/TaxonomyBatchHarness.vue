<script setup lang="ts">
import { onMounted } from 'vue';
import { useModuleStore } from '@/stores/modules';
import type { Module } from '@/constant/modules';

const props = defineProps<{
  moduleType: Module;
  entries: string[];
  year: string;
}>();

const moduleStore = useModuleStore();

onMounted(async () => {
  await moduleStore.getSubmoduleTaxonomiesBatch(
    props.moduleType,
    props.entries,
    props.year,
  );
});
</script>

<template>
  <div>harness-ready</div>
</template>
