<template>
  <q-page class="module-page">
    <module-title :type="currentModuleType" />
    <module-charts :type="currentModuleType" />
  </q-page>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { computed } from 'vue';

import ModuleTitle from 'src/components/organisms/module/ModuleTitle.vue';
import ModuleCharts from 'src/components/organisms/module/ModuleCharts.vue';
const $route = useRoute();
const currentModuleType = computed(() => $route.params.module as string);
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;
.module-page {
  padding-top: tokens.$template-padding-y;
  gap: tokens.$template-gap;
  display: flex;
  flex-direction: column;
}
</style>
