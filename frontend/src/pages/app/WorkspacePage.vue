<script setup lang="ts">
import { useYearConfigStore } from 'src/stores/yearConfig';
import { useWorkspaceStore } from 'src/stores/workspace';
import { onMounted } from 'vue';
const yearConfigStore = useYearConfigStore();
const workspaceStore = useWorkspaceStore();

const fetchYearConfig = async () => {
  await yearConfigStore.fetchConfig(workspaceStore.selectedYear);
};

onMounted(async () => {
  await fetchYearConfig();
});
</script>

<template>
  <router-view />
</template>
