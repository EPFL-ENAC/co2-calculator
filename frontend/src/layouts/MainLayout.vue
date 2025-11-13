<script setup lang="ts">
import Co2Header from 'src/components/layout/Co2Header.vue';
import { useAuthStore } from 'src/stores/auth';
import { storeToRefs } from 'pinia';

const authStore = useAuthStore();
const { user } = storeToRefs(authStore);
</script>

<template>
  <q-layout view="lHh Lpr lFf">
    <Co2Header v-if="user" />

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>
