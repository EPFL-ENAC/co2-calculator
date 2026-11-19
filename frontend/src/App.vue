<template>
  <DemoInstanceNotice v-if="showDemoNotice" @continue="onContinue" />
  <SessionUnavailableNotice v-else-if="auth.sessionUnavailable" />
  <router-view v-else />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { runtimeConfig } from '@/config/runtime';
import DemoInstanceNotice from '@/pages/DemoInstanceNotice.vue';
import SessionUnavailableNotice from '@/pages/SessionUnavailableNotice.vue';
import { useAuthStore } from '@/stores/auth';
import { dismissDemoNotice, isDemoNoticeDismissed } from '@/utils/demoMode';

const auth = useAuthStore();
const showDemoNotice = ref(runtimeConfig.demoMode && !isDemoNoticeDismissed());

function onContinue() {
  dismissDemoNotice();
  showDemoNotice.value = false;
}
</script>
