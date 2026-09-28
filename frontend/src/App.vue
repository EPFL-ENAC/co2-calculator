<template>
  <DemoInstanceNotice v-if="showDemoNotice" @continue="onContinue" />
  <router-view v-else />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { runtimeConfig } from '@/config/runtime';
import DemoInstanceNotice from '@/pages/DemoInstanceNotice.vue';
import { dismissDemoNotice, isDemoNoticeDismissed } from '@/utils/demoMode';

const showDemoNotice = ref(runtimeConfig.demoMode && !isDemoNoticeDismissed());

function onContinue() {
  dismissDemoNotice();
  showDemoNotice.value = false;
}
</script>
