<script setup lang="ts">
import { useYearConfigStore } from 'src/stores/yearConfig';
import { useWorkspaceStore } from 'src/stores/workspace';
import { onMounted } from 'vue';
import { onBeforeRouteUpdate } from 'vue-router';
import { loadWorkspaceFromRoute } from 'src/router/guards/validateUnitGuard';

const yearConfigStore = useYearConfigStore();
const workspaceStore = useWorkspaceStore();

const fetchYearConfig = async () => {
  await yearConfigStore.fetchConfig(workspaceStore.selectedYear);
};

onMounted(async () => {
  await fetchYearConfig();
});

// `beforeEnter` does not re-run on param-only navigation, so switching unit or
// year via the home-page dropdowns is handled here: re-validate the workspace
// and reload the year configuration before the updated route resolves.
onBeforeRouteUpdate(async (to, from) => {
  if (
    to.params.unit === from.params.unit &&
    to.params.year === from.params.year
  ) {
    return true;
  }
  const result = await loadWorkspaceFromRoute(to);
  if (result !== true) return result;
  await fetchYearConfig();
  return true;
});
</script>

<template>
  <router-view />
</template>
