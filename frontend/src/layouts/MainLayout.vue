<script setup lang="ts">
import { computed } from 'vue';
import Co2Header from 'src/components/layout/Co2Header.vue';
import { useAuthStore } from 'src/stores/auth';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';
import { isBackOfficeRoute } from 'src/router/routes';
import Co2Sidebar from 'src/components/layout/Co2Sidebar.vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';

const authStore = useAuthStore();
const { user } = storeToRefs(authStore);
const route = useRoute();
const isBackOffice = computed(() => isBackOfficeRoute(route));
</script>

<template>
  <q-layout view="lHh Lpr lFf">
    <Co2Header v-if="user" />

    <q-page-container class="co2-page-container">
      <aside class="sidebar-wrapper">
        <Co2Sidebar v-if="isBackOffice" :items="BACKOFFICE_NAV" />
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
