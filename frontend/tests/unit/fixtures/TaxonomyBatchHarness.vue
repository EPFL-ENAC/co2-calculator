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
  <div data-testid="store-error">{{ moduleStore.state.error ?? '' }}</div>
  <ul>
    <li
      v-for="entry in props.entries"
      :key="entry"
      :data-testid="`taxonomy-${entry}`"
    >
      {{ moduleStore.state.taxonomySubmodule[entry] ? 'resolved' : 'missing' }}
    </li>
  </ul>
</template>
