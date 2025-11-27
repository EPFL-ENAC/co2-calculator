<template>
  <q-page class="module-page">
    <module-title :type="currentModuleType" />
  </q-page>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { computed } from 'vue';

import ModuleTitle from 'src/components/organisms/module/ModuleTitle.vue';
const $route = useRoute();
const currentModuleType = computed(() => $route.params.module as string);
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;
.module-page {
  padding-top: tokens.$layout-page-padding-y;
}
</style>
