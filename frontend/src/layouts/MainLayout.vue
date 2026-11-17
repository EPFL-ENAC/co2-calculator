<script setup lang="ts">
import { computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';
import { isBackOfficeRoute } from '@/router/routes';
import { shellParts } from '@/router/authenticatedShell';
import { BACKOFFICE_NAV } from '@/constant/navigation';

const authStore = useAuthStore();
const { user } = storeToRefs(authStore);
const route = useRoute();
const isBackOffice = computed(() => isBackOfficeRoute(route));
const isModuleRoute = computed(() =>
  ['module', 'results'].includes(String(route.name)),
);
</script>

<template>
  <q-layout view="lHh Lpr lFf">
    <!-- The login page draws this layout without them; the router loads them
         before any signed-in page is shown (see authenticatedShell.ts). -->
    <component :is="shellParts().Co2Header" v-if="user" />

    <q-page-container class="co2-page-container">
      <aside class="sidebar-wrapper">
        <component
          :is="shellParts().Co2Sidebar"
          v-if="isBackOffice"
          :items="BACKOFFICE_NAV"
        />
        <component
          :is="shellParts().Co2ModuleSidebar"
          v-else-if="isModuleRoute"
        />
      </aside>
      <main class="content-wrapper">
        <router-view />
      </main>
    </q-page-container>
  </q-layout>
</template>

<style lang="scss" scoped>
.co2-page-container {
  display: flex !important;
  height: 100vh;
  box-sizing: border-box;
  overflow: hidden;
  align-items: stretch;
}

.sidebar-wrapper {
  flex-shrink: 0;
  overflow-y: auto;
}

.content-wrapper {
  flex: 1;
  overflow-y: auto;
  min-width: 0; // prevent flex blowout from wide content
}
</style>
