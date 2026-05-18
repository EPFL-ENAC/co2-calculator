<template>
  <q-layout view="lHh Lpr lFf" class="print-layout">
    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { providePrintMode } from 'src/composables/print/usePrintMode';

providePrintMode(true);
</script>

<style>
@page {
  size: A4 portrait;
  margin: 0;
}

body {
  background: white;
}

@media print {
  body {
    background: white !important;
  }
}
</style>

<style scoped>
.print-layout {
  background: white;
}
</style>
