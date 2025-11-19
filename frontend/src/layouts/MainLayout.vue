<script setup lang="ts">
import Co2Header from 'src/components/layout/Co2Header.vue';
import { useAuthStore } from 'src/stores/auth';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';
import { isBackOfficeRoute, isSystemRoute } from 'src/router/routes';
import Co2Sidebar from 'src/components/layout/Co2Sidebar.vue';
import { BACKOFFICE_NAV, SYSTEM_NAV } from 'src/constant/sidebarNavigation';

const authStore = useAuthStore();
const { user } = storeToRefs(authStore);
const route = useRoute();
const isBackOffice = isBackOfficeRoute(route);
const isSystem = isSystemRoute(route);
</script>

<template>
  <q-layout view="lHh Lpr lFf">
    <Co2Header v-if="user" />

    <q-page-container class="co2-page-container">
      <template v-if="isBackOffice || isSystem">
        <Co2Sidebar v-if="isBackOffice" :items="BACKOFFICE_NAV" />
        <Co2Sidebar v-if="isSystem" :items="SYSTEM_NAV" />
      </template>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<style lang="scss" scoped>
.co2-page-container {
  display: grid;
  width: 100%;
  height: 100%;
  grid-template-columns: auto 1fr;
  grid-template-areas: 'sidebar content';

  .co2-sidebar {
    grid-area: sidebar;
  }
  .co2-content {
    grid-area: content;
  }
}
</style>
