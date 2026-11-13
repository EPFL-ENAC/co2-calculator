<template>
  <MissingConfigNotice
    v-if="missingConfig.length > 0 || invalidConfig.length > 0"
    :missing-keys="missingConfig"
    :invalid-keys="invalidConfig"
  />
  <DemoInstanceNotice v-else-if="showDemoNotice" @continue="onContinue" />
  <router-view v-else />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { invalidConfig, missingConfig, runtimeConfig } from '@/config/runtime';
import DemoInstanceNotice from '@/pages/DemoInstanceNotice.vue';
import MissingConfigNotice from '@/pages/MissingConfigNotice.vue';
import { dismissDemoNotice, isDemoNoticeDismissed } from '@/utils/demoMode';

const { t } = useI18n();
// The tab title names the institution, so it is set at runtime (#3244).
// setLanguageCookieGuard sets it again when the language changes.
document.title = t('app_document_title');

const showDemoNotice = ref(runtimeConfig.demoMode && !isDemoNoticeDismissed());

function onContinue() {
  dismissDemoNotice();
  showDemoNotice.value = false;
}
</script>
