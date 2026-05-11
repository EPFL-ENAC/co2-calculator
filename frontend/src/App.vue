<template>
  <router-view />
</template>

<script setup lang="ts">
import { watch } from 'vue';
import { useColorblindStore } from 'src/stores/colorblind';
import { colorblindMode } from 'src/constant/charts';
import { storeToRefs } from 'pinia';

// Keep the module-level colorblindMode ref in sync with the Pinia store.
// Charts import colorblindMode directly from charts.ts; this bridge ensures
// toggling the store propagates reactively to all chart computed refs.
const colorblindStore = useColorblindStore();
const { enabled } = storeToRefs(colorblindStore);
watch(enabled, (v) => (colorblindMode.value = v), { immediate: true });
</script>
